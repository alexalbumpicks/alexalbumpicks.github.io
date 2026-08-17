#!/usr/bin/env python3
"""Close the art/audio gaps the bulk resolver left behind.

The bulk pass failed on these for three distinct reasons, so this pass attacks each:
  1. The album is on Apple but only outside the US storefront (Japanese/Taiwanese
     releases) -> retry the search against JP/TW/GB/FR.
  2. Apple has the album but Deezer had no matching album, so no track name was ever
     chosen -> rank Apple's tracklist against the artist's Deezer top-tracks instead.
  3. Apple doesn't carry the record at all (Constellation, Mule Musiq) -> art from the
     Cover Art Archive; audio simply stays empty rather than pointing somewhere wrong.

Confirmed collection IDs are hard-coded: fuzzy matching already missed these once, and
a wrong preview is worse than a missing one.

Usage: python3 gapfill.py [--apply]
"""
import json, re, sys, time, unicodedata, urllib.parse, urllib.request

DATA = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/data.js'
OUT = '/tmp/gapfill.json'
UA = {'User-Agent': 'indie-rock-timeline/1.0 (xavjiang@gmail.com)'}

# (year, artist, album, apple_collection_id | None, apple_search_term | None)
TARGETS = [
    (2000, 'Godspeed You! Black Emperor', 'Lift Your Skinny Fists Like Antennas to Heaven', None, None),
    (2001, 'Daft Punk', 'Discovery', 697194953, None),
    (2003, '椎名林檎', '加爾基 精液 栗ノ花', None, '椎名林檎 加爾基 精液 栗ノ花'),
    (2003, 'The Unicorns', 'Who will cut our hair when we are gone?', 897570398, None),
    (2004, 'M.I.A.', 'Piracy Funds Terrorism', None, 'M.I.A. Piracy Funds Terrorism'),
    (2005, '陈绮贞', '华丽的冒险', 818157917, None),
    (2005, 'Nujabes', 'Modal Soul', None, 'Nujabes Modal Soul'),
    (2005, 'Newfound interests in Connecticut', 'Tell me about the long dark path home',
     None, 'A Newfound Interest in Connecticut'),
    (2006, 'Brand New', 'The Devil and God Are Raging Inside Me', 1440754537, None),
    (2007, 'Justice', 'Cross', 259751732, None),
    (2008, 'Grouper', 'Dragging a Dead Deer Up the Hill', 434319411, None),
    (2008, 'DJ Sprinkles', 'Midtown 120 Blues', None, 'DJ Sprinkles Midtown 120 Blues'),
    (2008, 'Jazz Liberatorz', "Clin d'oeil", None, "Jazz Liberatorz Clin d'oeil"),
]

STOREFRONTS = ['US', 'JP', 'TW', 'GB', 'FR', 'DE']
SKIP_TRACK = ('remix', 'version', 'live', 'edit', 'instrumental', 'a cappella', 'acapella',
              'reprise', 'interlude', 'skit', 'intro', 'outro', 'untitled')

# SKIP_TRACK matched as a plain substring, which is why Love and Rockets' 'So Alive' - the one
# song on that record anybody knows - was dropped as a live take: 'live' is inside 'alive'.
# 'edit' inside 'Credit' and 'intro' inside 'Introspection' are the same trap.
#
# Only the *leading* edge is a word boundary, so the plurals these words actually appear in
# still match: 'Remixes', 'Edits', 'Alternate Versions'. Trailing \b would lose all three.
SKIP_RE = re.compile(r'\b(' + '|'.join(re.escape(w) for w in SKIP_TRACK) + r')', re.I)

# Apple suffixes track names in ways Deezer does not: every track on a reissue is
# '... (Remastered)' or '(2011 Remaster)', and guest credits are '(feat. X)' where Deezer
# just writes the title. norm() on either side then never agreed, so *every* remastered
# album silently lost its play counts and fell back to track one - which is how Boys for
# Pele picked its opener over 'Professional Widow'.
#
# Only ever used for the ranking lookup. The name Apple gave is still what gets recorded.
EDITION_RE = re.compile(
    r'\s*[\(\[][^\)\]]*\b(remaster(ed)?|reissue|deluxe|mono|stereo|\d{4} mix'
    r'|feat\.?|featuring|with)\b[^\)\]]*[\)\]]',
    re.I)


def rank_key(title):
    """norm() for the play-count lookup, with any edition/guest parenthetical dropped."""
    return norm(EDITION_RE.sub('', title or ''))


def amp(s):
    """'&', '+' and 'and' folded to one spelling.

    norm() drops punctuation but keeps letters, so '&' disappears while 'and' stays and the
    two forms of the same title never compare equal. That bit three separate places - the
    album scorer, the artist-name check in resolve2020s, and caa_art below - so the fold
    lives here, next to norm, rather than in any one of them.

    Only folded between spaces for '+', so a '+' that belongs to a name survives.
    """
    return re.sub(r'\s+[&+]\s+|\s*&\s*', ' and ', s or '')


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^0-9a-z　-鿿]', '', s.lower())


def get(url, tries=5):
    """iTunes answers 403 when it thinks we're hammering it, so back off generously."""
    for n in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            if n == tries - 1:
                return {}
            time.sleep(3 * (n + 1))


def head_ok(url):
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, method='HEAD', headers=UA), timeout=20)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------------ apple

def apple_album(term, album):
    """Search every storefront until one carries the record."""
    for country in STOREFRONTS:
        r = get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': term, 'entity': 'album', 'limit': 20, 'country': country}))
        for x in r.get('results', []):
            cn = x.get('collectionName') or ''
            if norm(album) in norm(cn) or norm(cn) in norm(album):
                return x.get('collectionId'), country, cn
        time.sleep(1.5)
    return None, None, None


def apple_tracks(cid, country='US'):
    r = get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
        {'id': cid, 'entity': 'song', 'limit': 80, 'country': country}))
    res = r.get('results', [])
    if not res:
        return None, []
    return res[0], [x for x in res[1:] if x.get('previewUrl')]


# ----------------------------------------------------------------------- deezer

def deezer_ranks(artist):
    """Artist's most-played tracks. Used to rank Apple's tracklist when the bulk
    resolver couldn't find the album on Deezer at all.

    Deezer carries duplicate profiles under the same name - an artist Madonna with 177 fans
    and no top tracks at all, a Tori Amos with 34 - and search returns those *ahead* of the
    real one. Taking the first exact name match therefore handed back an empty ranking for
    some of the most obvious artists on the list, and every one of their albums quietly fell
    through to the track-one fallback.

    nb_fan settles it and is not close: 4,892,230 against 177 for Madonna. Take the biggest
    exact match rather than the first, and only then fetch the tracks.
    """
    a = get('https://api.deezer.com/search/artist?' + urllib.parse.urlencode(
        {'q': artist, 'limit': 5}))
    same = [art for art in a.get('data', []) if norm(art['name']) == norm(artist)]
    if not same:
        return {}
    best = max(same, key=lambda art: art.get('nb_fan') or 0)
    t = get(f"https://api.deezer.com/artist/{best['id']}/top?limit=50")
    return {rank_key(x['title']): x.get('rank', 0) for x in t.get('data', [])}


RUNT = 0.6   # a track under this share of the album's median length is a prelude


def _no_runts(pool):
    """`pool` without the preludes, judged against the album's own median length.

    SKIP_TRACK only catches tracks that *say* they are intros. Plenty don't: Illmatic opens
    on 'The Genesis', a minute and a half of Wild Style dialogue, and I Can Hear the Heart
    Beating As One opens on 'Return to Hot Chicken', an instrumental clearing of the throat.
    Both got picked whenever Deezer had no play counts, because the fallback took track 1
    on name alone.

    An absolute cutoff can't do this: at 1:45 and 1:40 these two are longer than plenty of
    real songs, and any threshold high enough to catch them also eats Guided by Voices. The
    album's own median is the scale that works - a prelude is short *relative to the record
    it opens*, while Bee Thousand's median is short too, so its openers survive.
    """
    ms = sorted(t.get('trackTimeMillis') or 0 for t in pool)
    if len(ms) < 4:
        return pool
    med = ms[len(ms) // 2]
    return [t for t in pool if (t.get('trackTimeMillis') or 0) >= med * RUNT] or pool


def pick(tracks, ranks):
    """Most-played track on the album; failing that, the first real one."""
    clean = [t for t in tracks if not SKIP_RE.search(t.get('trackName') or '')]
    pool = clean or tracks
    scored = [(ranks.get(rank_key(t['trackName']), 0), t) for t in pool]
    best = max(scored, key=lambda x: x[0])
    if best[0] > 0:
        return best[1]
    return min(_no_runts(pool), key=lambda t: t.get('trackNumber') or 99)


# ------------------------------------------------------------------ cover art archive

def caa_art(artist, album):
    q = urllib.parse.urlencode({
        'query': f'releasegroup:"{album}" AND artist:"{artist}"', 'fmt': 'json', 'limit': 5})
    r = get(f'https://musicbrainz.org/ws/2/release-group?{q}')
    time.sleep(1.2)
    for rg in r.get('release-groups', []):
        # amp() on both sides: MusicBrainz files Sandy Bull's record as 'Fantasias for
        # Guitar & Banjo' where the sheet writes 'and', and without the fold the only
        # cover art that exists for it is unreachable.
        want, got = norm(amp(album)), norm(amp(rg.get('title')))
        if not (want in got or got in want):
            continue
        url = f"https://coverartarchive.org/release-group/{rg['id']}/front-500"
        if head_ok(url):
            return url
        rel = get(f"https://musicbrainz.org/ws/2/release?release-group={rg['id']}&fmt=json&limit=10")
        time.sleep(1.2)
        for x in rel.get('releases', []):
            url = f"https://coverartarchive.org/release/{x['id']}/front-500"
            if head_ok(url):
                return url
    return None


# ------------------------------------------------------------------------ driver

def main():
    out = {}
    for year, artist, album, cid, term in TARGETS:
        country = 'US'
        canon = None
        if not cid:
            cid, country, canon = apple_album(term or f'{artist} {album}', album)
        rec = {'year': year, 'artist': artist, 'album': album,
               'art': None, 'audio': None, 'track': None, 'canon': canon, 'notes': []}

        if cid:
            coll, tracks = apple_tracks(cid, country)
            if coll:
                rec['canon'] = coll.get('collectionName')
                rec['art'] = (coll.get('artworkUrl100') or '').replace('100x100bb', '600x600bb') or None
            if tracks:
                t = pick(tracks, deezer_ranks(artist))
                rec['track'] = t['trackName']
                rec['audio'] = t['previewUrl']
            else:
                rec['notes'].append('apple album has no previewable tracks')
        else:
            rec['notes'].append('not on Apple in any storefront')

        if not rec['art']:
            rec['art'] = caa_art(artist, album)
            rec['notes'].append('art:coverartarchive' if rec['art'] else 'art:NONE')

        out[f'{year}|{artist}|{album}'] = rec
        print(f"{year} {artist} - {album}\n    art  : {rec['art']}\n"
              f"    audio: {rec['track']} -> {rec['audio']}\n"
              f"    canon: {rec['canon']}"
              + (f"\n    notes: {', '.join(rec['notes'])}" if rec['notes'] else ''), flush=True)
        json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
        time.sleep(1.0)

    print(f"\nart {sum(1 for v in out.values() if v['art'])}/{len(out)}  "
          f"audio {sum(1 for v in out.values() if v['audio'])}/{len(out)}")


if __name__ == '__main__':
    main()
