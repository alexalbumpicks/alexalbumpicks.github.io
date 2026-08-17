#!/usr/bin/env python3
"""Second pass over the 2010s albums the bulk resolver left incomplete.

Unlike gapfill.py, the target list isn't hand-written - it's every cache record
missing art or audio. Most of those are transient: iTunes answers 403 under load and
the bulk pass only backs off 1.5s, so an album that plainly exists on Apple ends up
with no `canon` and Cover Art Archive art. This pass re-asks slowly, and only then
tries the genuinely-different strategies:

  1. album on Apple outside the US storefront    -> retry against JP/GB/FR/DE/TW
  2. Apple has it but Deezer had no album, so no track was ever chosen
                                                 -> rank Apple's own tracklist by the
                                                    artist's Deezer top tracks
  3. not on Apple at all                         -> Deezer cover_big, then Cover Art
                                                    Archive; audio stays empty rather
                                                    than pointing somewhere wrong

Art preference is Apple > Deezer > Cover Art Archive, and records that already have CAA
art are retried too: CAA's /front-500 intermittently 500s for the *same* URL minutes
apart, so a cover sitting on it will randomly fail to load. Deezer's cover_big is on a
static token-free CDN, unlike its preview URLs, which expire in ~24h.

Usage: python3 gapfill2010s.py
"""
import json, os, re, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gapfill as G
import resolve2000s as R

CACHE = '/tmp/cache2010s.json'
OUT = '/tmp/gapfill2010s.json'

# Records Apple carries under a name no search from the sheet's spelling can reach.
# Keyed by cache key; canon is left alone so the entry keeps the title it should have.
APPLE_ID = {
    # Mills's 2010 debut came out as Break Mirrors and sits on Apple self-titled
    # (2010-07-06, 9 tracks), so searching for Break Mirrors finds only a remix single.
    '2010|Blake Mills|Blake Mills': 476483129,
}


def is_caa(url):
    return bool(url) and 'coverartarchive.org' in url


# gapfill.apple_album takes the first collection whose name merely overlaps the album's,
# with no artist check at all, which on a decade-sized batch is catastrophic: "MAGDALENE"
# matched "Magdalene (Live) - Single", "Charli" matched "OUT OUT (feat. Charli XCX &
# Saweetie) - Single", "Pure Heroine" matched "Lullaby Renditions of Lorde". Everything
# below is the strict scoring resolve2000s.itunes_album uses, plus the categories that
# only show up once you search for 2010s pop.
# Phrases, not bare words: 'sleep' on its own rejects WHEN WE ALL FALL ASLEEP, WHERE DO
# WE GO?, and 'study' would reject anything with "Studying" in the title.
REJECT = R.REJECT + ('renditions', 'performs', 'playlist', 'slowed', 'reverb', 'rework',
                     '8-bit', 'string quartet', 'workout mix', 'study music',
                     'sleep music', 'music for sleep')
# 'edit' rather than 'radio edit' would demote every "(Deluxe Edition)", and 'ep' as a
# bare substring fires on "deep" and "September".
# 'pt.'/'vol.' keep Robyn's Body Talk, Pt. 3 from standing in for Body Talk. An album
# whose own title carries one still scores on the exact-match path.
# "Speak Now (Taylor's Version)" is a 2023 re-recording: right songs, wrong performances,
# and the previews would be from a record made 13 years after the one being listed.
# 'expanded' drops to 1: an expanded edition is the same performances, and for an album
# the sheet abbreviates - Fiona Apple's Idler Wheel - it may be all Apple carries.
DEMOTE = tuple((w, 1 if w == 'expanded' else p) for w, p in R.DEMOTE) + (
    ('single', 6), ('radio edit', 3), ('pt.', 2), ('vol.', 2),
    ("'s version", 6), ('re-recorded', 6))


def suffix_ok(name, want):
    """True when `name` is `want` plus an *edition marker*, not plus another word.

    Normalising both sides throws away the punctuation that distinguishes the two, and
    the difference matters: "Teen Dream (Bonus Track Version)" is Teen Dream, but "The
    Fame Monster" is not The Fame and "Turn Out the Lights" is not "Turn Out". So the
    remainder is read off the raw title, and has to open with a bracket or a dash.
    """
    for i in range(len(name)):
        if G.norm(name[:i + 1]) == want:
            rest = name[i + 1:].lstrip()
            return not rest or rest[0] in '([{-–—:,/|'
    return False


def censored_match(name, want):
    """Apple bowdlerises titles: NFR! is listed as "Norman F*****g Rockwell".

    G.norm drops the asterisks and leaves "normanfgrockwell", which matches nothing, so
    the run of stars is read as the wildcard it is.
    """
    if '*' not in name:
        return False
    keep = re.sub(r'[^a-z0-9*]', '', name.lower())
    return re.fullmatch(re.sub(r'\*+', '.*', re.escape(keep).replace(r'\*', '*')),
                        want) is not None


def score_coll(name, album):
    """How well an Apple collection name answers to `album`. 0 means no.

    Only *suffix* padding counts. Apple appending an edition marker is normal, so
    "Teen Dream (Bonus Track Version)" answers to Teen Dream; anything else does not.
    Apple returning something shorter means a different record - "When I Get Home" must
    not settle for "Home", nor "To Be Kind" for "Be Kind" - and padding on the *left* is
    someone else's record borrowing the title, as in "Starhand Visions" for Visions or
    "The Atrocity Exhibition - Exhibit A" for Atrocity Exhibition.
    """
    low = (name or '').lower()
    if not low or any(w in low for w in REJECT):
        return 0
    base, want, whole = R.base_title(name), G.norm(album), G.norm(name)
    if 'feat.' in low and base != want:
        return 0
    if base == want or whole == want or censored_match(name, want):
        s = 6.0
    elif whole.startswith(want) and suffix_ok(name, want):
        s = 3.0
    elif whole.startswith(want) and len(want) >= 12:
        # The sheet abbreviates long titles - "The Idler Wheel" for a record Apple lists
        # under all twenty-three words of its name. Below twelve characters a bare word
        # suffix is far more likely to be a different album ("The Fame" / The Fame
        # Monster), so only long titles get this, and only if nothing scored higher.
        s = 2.0
    else:
        return 0
    for word, pen in DEMOTE:
        if word in low:
            s -= pen
    return s if s > 0 else 0


def apple_album_strict(artist, album):
    """(collectionId, country, collectionName) - scored, not first-hit.

    Returns (None, None, None) rather than a guess: a wrong preview is worse than a
    silent one, and the Deezer/CAA art fallbacks still run.
    """
    for country in G.STOREFRONTS:
        best, best_s = None, 0
        for term in (f'{artist} {album}', album):
            try:
                r = G.get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
                    {'term': term, 'entity': 'album', 'limit': 25, 'country': country}))
            except Exception:
                continue
            for x in r.get('results', []):
                an = G.norm(x.get('artistName'))
                if not (G.norm(artist) in an or an in G.norm(artist)):
                    continue
                s = score_coll(x.get('collectionName'), album)
                if s > best_s:
                    best, best_s = x, s
            if best:
                break
            time.sleep(0.5)
        if best:
            return best.get('collectionId'), country, best.get('collectionName')
        time.sleep(1.5)
    return None, None, None


def apple_album_via_catalogue(artist, album):
    """Find an album by walking the artist's catalogue instead of searching for it.

    The iTunes *search* index has real holes - it returns nothing at all for
    'St. Vincent Masseduction', and MASSEDUCTION is absent from the 25 albums it
    gives for 'St. Vincent' - but the *lookup* endpoint enumerates the same artist's
    catalogue and has it. Six 2010s records were written off as 'not on Apple' on the
    strength of the search endpoint alone; every one of them is really there.

    Returns (collectionId, collectionName) or (None, None).
    """
    try:
        a = G.get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': artist, 'entity': 'musicArtist', 'limit': 8}))
    except Exception:
        return None, None
    ids = [x['artistId'] for x in a.get('results', [])
           if G.norm(x.get('artistName')) == G.norm(artist)]
    time.sleep(1.0)

    best, best_s = None, 0
    for aid in ids[:3]:
        try:
            r = G.get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
                {'id': aid, 'entity': 'album', 'limit': 200}))
        except Exception:
            continue
        for x in r.get('results', []):
            if not x.get('collectionName') or not x.get('collectionId'):
                continue
            # Same scoring as the search path, so "Nina Kraviz Presents MASSEDUCTION
            # Rewired" can't outrank MASSEDUCTION.
            s = score_coll(x.get('collectionName'), album)
            if s > best_s:
                best, best_s = x, s
        time.sleep(1.0)
    return (best['collectionId'], best['collectionName']) if best else (None, None)


def main():
    cache = json.load(open(CACHE))
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    # Also re-ask for anything whose cached title doesn't answer to the album asked for.
    # A canon like "Honey - Single" or "Starhand Visions" means the bulk pass matched the
    # wrong collection, so its art and audio point at the wrong record too.
    todo = [(k, v) for k, v in cache.items()
            if not (v.get('art') and v.get('audio')) or is_caa(v.get('art'))
            or not score_coll(v.get('canon'), v['album'])]
    print(f'{len(todo)} to retry\n', flush=True)

    for n, (key, v) in enumerate(todo, 1):
        if key in out:
            continue
        artist, album, year = v['artist'], v['album'], v['year']
        rec = {'year': year, 'artist': artist, 'album': album,
               'art': None, 'audio': None, 'track': None, 'canon': None, 'notes': []}

        if key in APPLE_ID:
            cid, country, canon = APPLE_ID[key], 'US', None
            rec['notes'].append('found:override')
        else:
            cid, country, canon = apple_album_strict(artist, album)
        if not cid:  # some records aren't in the search index at all
            cid, canon = apple_album_via_catalogue(artist, album)
            if cid:
                country = 'US'
                rec['notes'].append('found:catalogue')
        if cid:
            coll, tracks = G.apple_tracks(cid, country or 'US')
            # A short album title can match the wrong collection - searching "LP1"
            # finds something previewless while FKA twigs' real LP1 sits in her
            # catalogue. An empty tracklist means the match was wrong, not that the
            # record has no previews, so fall through rather than give up.
            if not tracks:
                alt, alt_canon = apple_album_via_catalogue(artist, album)
                if alt and alt != cid:
                    coll2, tracks2 = G.apple_tracks(alt, 'US')
                    if tracks2:
                        cid, canon, coll, tracks = alt, alt_canon, coll2, tracks2
                        country = 'US'
                        rec['notes'].append('found:catalogue')
            if coll:
                rec['canon'] = coll.get('collectionName')
                rec['art'] = (coll.get('artworkUrl100') or '').replace(
                    '100x100bb', '600x600bb') or None
            if tracks:
                # Prefer the track the bulk pass already picked from Deezer's ranking;
                # only fall back to re-ranking when that track isn't on Apple's list.
                want = G.norm(v.get('track') or '')
                hit = [t for t in tracks if G.norm(t.get('trackName')) == want] if want else []
                t = hit[0] if hit else G.pick(tracks, G.deezer_ranks(artist))
                rec['track'] = t['trackName']
                rec['audio'] = t['previewUrl']
            else:
                rec['notes'].append('apple album has no previewable tracks')
            if country and country != 'US':
                rec['notes'].append(f'storefront:{country}')
        else:
            rec['notes'].append('not on Apple in any storefront')

        if not rec['art']:
            try:
                alb = R.deezer_album(artist, album, year)
                rec['art'] = (alb or {}).get('cover_big') or None
            except Exception:
                pass
            if rec['art']:
                rec['notes'].append('art:deezer')

        if not rec['art']:
            rec['art'] = G.caa_art(artist, album)
            rec['notes'].append('art:coverartarchive' if rec['art'] else 'art:NONE')

        out[key] = rec
        json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
        state = ('OK' if rec['art'] and rec['audio'] else
                 'PARTIAL ' + ','.join(rec['notes']))
        print(f'[{n}/{len(todo)}] {year} {artist} - {album}  {state}', flush=True)
        time.sleep(1.0)

    print(f"\nart {sum(1 for r in out.values() if r['art'])}/{len(out)}  "
          f"audio {sum(1 for r in out.values() if r['audio'])}/{len(out)}")


if __name__ == '__main__':
    main()
