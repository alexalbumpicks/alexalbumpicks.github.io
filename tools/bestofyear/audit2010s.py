#!/usr/bin/env python3
"""Check what build2010s.py *would* write before it writes it.

The first 2010s import went in with ~35 albums pointing at the wrong Apple record -
"MAGDALENE" resolved to "Magdalene (Live) - Single", "Charli" to "OUT OUT (feat. Charli
XCX & Saweetie) - Single" - because gapfill.apple_album takes the first collection whose
name merely overlaps and never checks the artist. The titles were only caught by reading
them afterwards, so this does that reading up front, on the merged cache+gapfill record
build2010s actually consumes.

Every title that differs from the sheet's is printed, split into the ones the strict
scorer vouches for and the ones it doesn't. The second list should be empty; anything in
it means the album, its art and its preview all belong to some other record.

Usage: python3 audit2010s.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# `sheet` first: build2000s puts /tmp on the path ahead of us, and an older copy of
# sheet.py lives there. Importing ours first pins it in sys.modules for everyone.
from sheet import records, fixed, sheet_year
import gapfill2010s as X
from build2010s import title_for

CACHE = '/tmp/cache2010s.json'
GAP = '/tmp/gapfill2010s.json'


def main():
    cache = json.load(open(CACHE))
    gap = json.load(open(GAP)) if os.path.exists(GAP) else {}
    recs, _ = records()

    ok, suspect, missing = [], [], []
    for r in recs:
        if not r.get('Year'):
            continue
        year = sheet_year(r)
        if not 2010 <= year <= 2019:
            continue
        title, artist = fixed(r)
        ck = f'{year}|{r["Act"]}|{r["Albums"]}'
        c = dict(cache.get(ck) or {})
        if not c:
            continue  # already in bestof-data.js, never resolved
        g = gap.get(ck)
        if g:
            for f in ('art', 'audio', 'track'):
                if g.get(f):
                    c[f] = g[f]
            c['canon'] = g.get('canon')

        used = title_for(title, c.get('canon'))
        if not (c.get('art') and c.get('audio')):
            missing.append(f'  {year} {artist} - {used}  '
                           f'{"no art " if not c.get("art") else ""}'
                           f'{"no audio" if not c.get("audio") else ""}')
        if used == title:
            continue
        line = f'  {year} {artist}\n      sheet: {title}\n      used : {used}'
        (ok if X.score_coll(c.get('canon'), title) else suspect).append(line)

    print(f'titles taken from Apple that differ from the sheet: {len(ok)}')
    for l in ok:
        print(l)
    print(f'\nSUSPECT - title does not answer to the album asked for: {len(suspect)}')
    for l in suspect:
        print(l)
    print(f'\nincomplete: {len(missing)}')
    for l in missing:
        print(l)


if __name__ == '__main__':
    main()
