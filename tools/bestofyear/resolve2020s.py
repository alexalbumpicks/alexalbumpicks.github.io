#!/usr/bin/env python3
"""Resolve album art + 30s audio preview for the 2020s Best-of-Year import (2020-2024).

One pass, not two. The 2010s needed resolve -> audit -> gapfill because the bulk
resolver searched Apple and took the first name that overlapped; roughly thirty-five
albums came back pointing at somebody else's single. This script starts from the
scoring that fixed that (score2020s.score_coll) and inverts the lookup order:

    catalogue first, search second.

The iTunes *search* index has holes that are not rate-limiting and do not go away on
retry. Searching for "The Avalanches Wildflower", "Blood Orange Freetown Sound",
"Robyn Honey" or "St. Vincent MASSEDUCTION" returns nothing usable, while the *lookup*
endpoint enumerating the same artist's catalogue has every one of them. Search is still
worth keeping as the fallback: it is the only way in for an artist whose name doesn't
match exactly (collaborations, alternate spellings), and for those the catalogue walk
finds no artistId at all.

Art preference is Apple > Deezer cover_big > Cover Art Archive. Audio is left empty
rather than pointed at a record that merely shares a title.

Usage: python3 resolve2020s.py [--set NAME] [--only YEAR]

The year set comes from importset.py and defaults to 2020s; nothing here is
decade-specific, so `--set pre2000` runs the same pass over those years.
"""
import json, os, re, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# `sheet` before anything that reaches resolve2000s: that module does
# sys.path.insert(0, '/tmp'), and an older copy of sheet.py lives there. Importing ours
# first pins it in sys.modules for every later import.
import importset
from sheet import records, fixed, fixed_year
import boy
import gapfill as G
import resolve2000s as R
from score2020s import score_coll

YEARS, CACHE = importset.pick()

# Records no lookup from the sheet's own spelling can reach, resolved by hand.
# Keyed by cache key (sheet year | sheet act | sheet album).
APPLE_ID = {
    # Apple carries Aoba romanised - 'Ichiko Aoba', 'Windswept Adan' - so neither the
    # artist walk nor the search finds anything from the Japanese spelling. The entry
    # keeps its Japanese name (as 椎名林檎 and 陈绮贞 already do) and points here.
    '2020|青葉市子|アダンの風': 1714304663,
    # One sheet row, two records issued together. Resolved against the first of the
    # pair; the entry is titled for both.
    '2024|Nicolas Jaar|Piedras 1&2': 1770305640,   # Piedras 1
    # Same shape: one row, two records. Apple has three EUSEXUAs - the album, the November
    # Afterglow companion and a re-issue of the first - and none of them answers to the
    # paired title, so the scorer is right to refuse all three. Pin the original.
    '2025|FKA Twigs|Eusexua/Eusexua Afterglow': 1767658574,
    '2020|Adrianne Lenker|songs/instrumentals': 1526437437,   # songs
    # Five records over two years. KiCk i is the one the series is named for.
    '2021|Arca|KicK i-v': 1511122250,
    # Apple has the 12 Rods EP twice - 'Gay?' and a reissue titled 'Gay (Ep)'. Both score,
    # and the reissue scores higher against the sheet's 'Gay? EP', so the walk picked it.
    # Pin the original; see the TITLE_FIX note in sheet.py.
    '1997|12 Rods|Gay? EP': 383641763,
    # Apple only carries this as 'Ventolin - EP'. The EP rule at the end of score_coll
    # docks six for a marker the sheet didn't ask for, which zeroes the only listing there is.
    '1995|Aphex Twin|Ventolin': 339045445,
    # Filed under Various Artists, so no artist walk reaches it and the search path's
    # artist check rejects it. The sheet credits Spector, which is how it is usually known.
    '1963|Phil Spector|A Christmas Gift for you from Phil Spector': 336036941,
    # Classical: Apple indexes by performer, never by composer, so 'Alfred Schnittke' walks
    # no catalogue. This is the Chamber Orchestra of Europe / Heinrich Schiff recording.
    '1977|Alfred Schnittke|Concerto Grosso No.1': 1452288564,
    # Apple spells the group singular and the album without the trailing stop:
    # 'R.N.A. Organism' / 'R.N.A.O Meets P.O.P.O'. Two mismatches at once, so pin it.
    '1980|R.N.A. Organisms|R.N.A. meets P.O.P.O.': 1734495662,
    # Apple lists Pink Moon twice. The plain plain-titled one wins on score but has no
    # playable track in any storefront; the remaster is the only one that previews. This is
    # the one case where the demoted edition is the right pick, so it can't come from the
    # scorer. title_for still writes the sheet's 'Pink Moon' - the remaster tag is stripped.
    '1972|Nick Drake|Pink Moon': 1440758653,
    # Apple files the record under its full 'Album - Generic Flipper'. The leading 'Album -'
    # is a title the sheet never asks for, so the scorer docks it out of contention and the
    # only other listing, a bare 'Generic', is the same record under a shorter name with no
    # previews. Pin the full one; title_for keeps the sheet's 'Generic Flipper'.
    '1982|Flipper|Generic Flipper': 1444076006,
}


def targets():
    _, _, _, entries = boy.load()
    have = {(boy.norm(x.get('title')), boy.norm(x.get('artist')))
            for x in entries if x.get('type') == 'album'}
    recs, _ = records()
    out = []
    for r in recs:
        if not r.get('Year') or fixed_year(r) not in YEARS:
            continue
        title, artist = fixed(r)
        if ((boy.norm(r['Albums']), boy.norm(r['Act'])) in have
                or (boy.norm(title), boy.norm(artist)) in have):
            continue
        out.append((fixed_year(r), r['Albums'], r['Act']))  # raw sheet strings = cache key
    return out


def _aname(s):
    """Artist name folded for comparison, '&' and 'and' the same way round.

    score_coll folds these for album titles; band names need it just as badly and this is
    the only place they get compared. The sheet writes 'Simon and Garfunkel', 'Nick Cave and
    the Bad Seeds', 'Richard and Linda Thompson', 'Siouxsie and the Banshees'; Apple writes
    every one of them with an ampersand. G.norm drops the '&' but keeps the letters of
    'and', so the two never matched and all four fell through to the search path, which
    then had no catalogue to walk and gave up.
    """
    return G.norm(G.amp(s))


def _exact_ids(name):
    try:
        a = G.get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': name, 'entity': 'musicArtist', 'limit': 8}))
    except Exception:
        return []
    return [x['artistId'] for x in a.get('results', [])
            if _aname(x.get('artistName')) == _aname(name)]


def artist_ids(artist):
    """Apple artistIds for an exact name match, best-effort.

    Exact only: a substring test lets 'Cindy Lee' pick up 'Cindy-Lee' and walk the wrong
    catalogue. When nothing matches exactly the search path takes over, which does its
    own looser artist check against the album's own credited name.

    Joint credits get a second pass over each partner alone. Apple has no combined entity
    for a duo record - 'billy woods & Kenny Segal' and 'JPEGMAFIA & Danny Brown' both match
    nothing - but files the album under one of the two, so walking each partner's catalogue
    finds it. Safe to be this loose here because the caller still has to clear score_coll
    on the album title; a partner's unrelated records score 0 and are ignored.
    """
    ids = _exact_ids(artist)
    if not ids and re.search(r'\s(?:&|and)\s|,', artist):
        for part in re.split(r'\s*(?:&|,)\s*|\s+and\s+', artist):
            if part.strip():
                ids += _exact_ids(part.strip())
            time.sleep(0.4)
    return ids


def album_via_catalogue(artist, album):
    """(collectionId, collectionName) by walking the artist's own releases."""
    best, best_s = None, 0
    for aid in artist_ids(artist)[:3]:
        time.sleep(0.8)
        try:
            r = G.get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
                {'id': aid, 'entity': 'album', 'limit': 200}))
        except Exception:
            continue
        for x in r.get('results', [])[1:]:
            if not (x.get('collectionName') and x.get('collectionId')):
                continue
            s = score_coll(x.get('collectionName'), album)
            if s > best_s:
                best, best_s = x, s
    return (best['collectionId'], best['collectionName']) if best else (None, None)


def album_via_search(artist, album):
    """(collectionId, country, collectionName) - scored, artist-checked, not first-hit."""
    for country in G.STOREFRONTS:
        best, best_s = None, 0
        for term in (f'{artist} {album}', album):
            try:
                r = G.get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
                    {'term': term, 'entity': 'album', 'limit': 25, 'country': country}))
            except Exception:
                continue
            for x in r.get('results', []):
                an = _aname(x.get('artistName'))
                if not (_aname(artist) in an or an in _aname(artist)):
                    continue
                s = score_coll(x.get('collectionName'), album)
                if s > best_s:
                    best, best_s = x, s
            if best:
                break
            time.sleep(0.5)
        if best:
            return best.get('collectionId'), country, best.get('collectionName')
        time.sleep(1.2)
    return None, None, None


def resolve(year, album, artist, key):
    rec = {'year': year, 'album': album, 'artist': artist,
           'art': None, 'audio': None, 'track': None, 'canon': None, 'notes': []}
    country = 'US'

    if key in APPLE_ID:
        cid, canon = APPLE_ID[key], None
        rec['notes'].append('found:override')
    else:
        cid, canon = album_via_catalogue(artist, album)
        if cid:
            rec['notes'].append('found:catalogue')
        else:
            cid, country, canon = album_via_search(artist, album)
            if cid:
                rec['notes'].append('found:search')
                if country != 'US':
                    rec['notes'].append(f'storefront:{country}')

    if cid:
        coll, tracks = G.apple_tracks(cid, country or 'US')
        if coll:
            rec['canon'] = coll.get('collectionName')
            rec['art'] = (coll.get('artworkUrl100') or '').replace(
                '100x100bb', '600x600bb') or None
        # Previews are licensed per storefront, so a record can be listed in the US with
        # every track unplayable while another country serves all of them. Pink Moon,
        # Clube da Esquina and Long Season each came back 'no previewable tracks' from the
        # US alone and are complete in JP/GB/DE. Only the tracks are refetched; the art and
        # the canonical name already came from the storefront that found the album.
        if not tracks:
            for alt in G.STOREFRONTS:
                if alt == (country or 'US'):
                    continue
                time.sleep(0.5)
                _, tracks = G.apple_tracks(cid, alt)
                if tracks:
                    rec['notes'].append(f'preview storefront:{alt}')
                    break
        if tracks:
            try:
                ranks = G.deezer_ranks(artist)
            except Exception:
                ranks = {}
            t = G.pick(tracks, ranks)
            rec['track'], rec['audio'] = t['trackName'], t['previewUrl']
        else:
            rec['notes'].append('no previewable tracks')
    else:
        rec['notes'].append('not on Apple')

    if not rec['art']:
        try:
            alb = R.deezer_album(artist, album, year)
            rec['art'] = (alb or {}).get('cover_big') or None
        except Exception:
            pass
        if rec['art']:
            rec['notes'].append('art:deezer')
    if not rec['art']:
        try:
            rec['art'] = G.caa_art(artist, album)
        except Exception:
            pass
        rec['notes'].append('art:coverartarchive' if rec['art'] else 'art:NONE')
    return rec


def main():
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1])
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [t for t in targets() if not only or t[0] == only]
    todo = [t for t in todo if f'{t[0]}|{t[2]}|{t[1]}' not in cache]
    print(f'{len(todo)} to resolve\n', flush=True)

    for n, (year, album, artist) in enumerate(todo, 1):
        key = f'{year}|{artist}|{album}'
        title, act = fixed({'Albums': album, 'Act': artist})
        try:
            rec = resolve(year, title, act, key)
        except Exception as ex:
            rec = {'year': year, 'album': title, 'artist': act, 'art': None,
                   'audio': None, 'track': None, 'canon': None,
                   'notes': [f'ERROR {type(ex).__name__}: {ex}']}
        cache[key] = rec
        json.dump(cache, open(CACHE, 'w'), indent=1, ensure_ascii=False)
        flag = '' if (rec['art'] and rec['audio']) else '  <-- ' + ','.join(rec['notes'])
        print(f'[{n}/{len(todo)}] {year} {act} - {title}{flag}', flush=True)
        time.sleep(0.4)

    done = [c for c in cache.values() if c['art'] and c['audio']]
    print(f'\ncomplete: {len(done)}/{len(cache)} have both art and audio')


if __name__ == '__main__':
    main()
