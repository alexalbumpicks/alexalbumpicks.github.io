#!/usr/bin/env python3
"""Resolve a slice of the 2010s target list into its own cache file.

resolve2010s.py walks the list front-to-back at roughly 40s an album, which is ~100
minutes for the decade. This runs additional workers over other slices so the wall
time comes down. Each worker owns a *separate* cache file: the caches are rewritten
whole after every record, so two processes sharing one would lose each other's work.
merge2010s.py folds them back together.

Usage: python3 shard2010s.py <cache-suffix> <start-index> <end-index>
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet import fixed
import resolve2000s as R
import resolve2010s as T


def main():
    suffix, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    cache_path = f'/tmp/cache2010s_{suffix}.json'
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    todo = T.targets()[lo:hi]

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
                    url, _ = R.itunes_preview(artist, top['title'], album, cid)
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
        json.dump(cache, open(cache_path, 'w'), indent=1, ensure_ascii=False)
        flag = '' if (rec['art'] and rec['audio']) else '  <-- ' + ','.join(rec['notes'])
        print(f'[{suffix} {n}/{len(todo)}] {year} {artist} - {album}{flag}', flush=True)
        time.sleep(0.4)


if __name__ == '__main__':
    main()
