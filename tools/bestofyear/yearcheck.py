#!/usr/bin/env python3
"""Flag albums whose sheet year disagrees with the actual release year.

The sheet is a personal listening log, so a record occasionally sits under the year
it was *heard* rather than released - which puts it on the wrong year-end list. This
only reports; moving an album is a judgement call and stays manual.

Deezer is the source because it answers release_date on the album endpoint and is far
more tolerant of bulk querying than the iTunes Search API.

Usage: python3 yearcheck.py [FROM] [TO]
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet import records, fixed
import resolve2000s as R

OUT = '/tmp/yearcheck.json'


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 2010
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 2019
    seen = json.load(open(OUT)) if os.path.exists(OUT) else {}

    recs, _ = records()
    rows = [r for r in recs if r.get('Year') and lo <= int(float(r['Year'])) <= hi]
    for n, r in enumerate(rows, 1):
        year = int(float(r['Year']))
        title, artist = fixed(r)
        key = f'{year}|{artist}|{title}'
        if key not in seen:
            try:
                alb = R.deezer_album(artist, title, year)
                seen[key] = (alb.get('release_date') or '')[:4] if alb else ''
            except Exception:
                seen[key] = ''
            json.dump(seen, open(OUT, 'w'), indent=1, ensure_ascii=False)
            time.sleep(0.3)
        got = seen[key]
        if got and abs(int(got) - year) >= 1:
            print(f'  sheet {year} vs release {got}   {artist} - {title}', flush=True)
        elif not got:
            print(f'  (no deezer match) {year} {artist} - {title}', flush=True)
    print(f'\nchecked {len(rows)} rows')


if __name__ == '__main__':
    main()
