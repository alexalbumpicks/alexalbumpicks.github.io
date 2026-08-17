#!/usr/bin/env python3
"""Resolve album art + 30s audio preview for the 2010s Best-of-Year import.

All the matching logic lives in resolve2000s.py; this only redefines the target
list (2010-2019, checked against bestof-data.js rather than data.js) and the cache
path, so the two decades can be re-run independently.

Usage: python3 resolve2010s.py [--only YEAR]
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boy
from sheet import records, fixed
import resolve2000s as R

CACHE = '/tmp/cache2010s.json'


def targets():
    _, _, _, entries = boy.load()
    have = {(boy.norm(x.get('title')), boy.norm(x.get('artist')))
            for x in entries if x.get('type') == 'album'}
    recs, _ = records()
    out = []
    for r in recs:
        if not r.get('Year'):
            continue
        y = int(float(r['Year']))
        if not (2010 <= y <= 2019):
            continue
        title, artist = fixed(r)
        # Check both spellings: the sheet's, and the corrected one that will
        # actually be written. Either colliding means the album is already there.
        if ((boy.norm(r['Albums']), boy.norm(r['Act'])) in have
                or (boy.norm(title), boy.norm(artist)) in have):
            continue
        out.append((y, r['Albums'], r['Act']))  # raw sheet strings = cache key
    return out


def main():
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1])
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = targets()
    if only:
        todo = [t for t in todo if t[0] == only]

    for n, (year, album, artist) in enumerate(todo, 1):
        key = f'{year}|{artist}|{album}'
        if key in cache:
            continue
        album, artist = fixed({'Albums': album, 'Act': artist})
        rec = {'year': year, 'album': album, 'artist': artist,
               'art': None, 'audio': None, 'track': None, 'canon': None, 'notes': []}
        try:
            art, cid, cname = R.itunes_album(artist, album)
            rec['art'], rec['canon'] = art, cname
            if not art:
                rec['art'] = R.musicbrainz_art(artist, album)
                rec['notes'].append('art:musicbrainz' if rec['art'] else 'art:NONE')

            alb = R.deezer_album(artist, album, year)
            if alb:
                tracks = [t for t in R.get(
                    f"https://api.deezer.com/album/{alb['id']}/tracks?limit=200")
                    .get('data', []) if t.get('rank') is not None]
                if tracks:
                    top = R.pick_track(tracks)
                    rec['track'] = top['title']
                    url, coll = R.itunes_preview(artist, top['title'], album, cid)
                    rec['audio'] = url
                    if not url:
                        rec['notes'].append('audio:NONE')
                else:
                    rec['notes'].append('audio:no-tracks')
            else:
                rec['notes'].append('audio:no-deezer-album')
        except Exception as ex:
            rec['notes'].append(f'ERROR {type(ex).__name__}: {ex}')

        cache[key] = rec
        json.dump(cache, open(CACHE, 'w'), indent=1, ensure_ascii=False)
        flag = '' if (rec['art'] and rec['audio']) else '  <-- ' + ','.join(rec['notes'])
        print(f'[{n}/{len(todo)}] {year} {artist} - {album}{flag}', flush=True)
        time.sleep(0.4)

    done = [c for c in cache.values() if c['art'] and c['audio']]
    print(f'\ncomplete: {len(done)}/{len(cache)} have both art and audio')


if __name__ == '__main__':
    main()
