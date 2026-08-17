#!/usr/bin/env python3
"""Check what build2020s.py *would* write, before it writes it.

The first 2010s import went in with ~35 albums pointing at the wrong Apple record and
the titles were only caught by reading them afterwards. This does that reading up front.

Three lists come out:
  - titles taken from Apple that differ from the sheet's, vouched for by the scorer
  - SUSPECT: a title the scorer will not vouch for. Expected to hold exactly the rows
    that stand for two records (they resolve against one half by design); anything else
    means the album, its art and its preview belong to somebody else.
  - incomplete: missing art or audio.

Usage: python3 audit2020s.py [--set NAME]
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# `sheet` first - see the note in build2020s.py.
import importset
from sheet import records, fixed, fixed_year, sheet_year
import score2020s as X
from build2020s import title_for

YEARS, CACHE = importset.pick()

# Rows where one sheet line stands for more than one record, so `canon` names only part
# of what the entry is called and the scorer is right to withhold its vote.
EXPECTED_SUSPECT = {
    ('Adrianne Lenker', 'songs / instrumentals'),
    ('Nicolas Jaar', 'Piedras 1 & 2'),
    ('Arca', 'KiCk i-v'),
    ('青葉市子', 'アダンの風'),
}


def main():
    cache = json.load(open(CACHE))
    recs, _ = records()

    ok, suspect, expected, missing = [], [], [], []
    for r in recs:
        if not r.get('Year') or fixed_year(r) not in YEARS:
            continue
        year = fixed_year(r)
        title, artist = fixed(r)
        ck = f'{sheet_year(r)}|{r["Act"]}|{r["Albums"]}'
        c = cache.get(ck)
        if not c:
            continue  # already in bestof-data.js, never resolved

        # `artist` too, or KEEP_SHEET_TITLE never fires here and the audit reports a title the
        # build does not actually write - which is worse than not reporting it at all.
        used = title_for(title, c.get('canon'), artist)
        if not (c.get('art') and c.get('audio')):
            missing.append(f'  {year} {artist} - {used}  '
                           f'{"no art " if not c.get("art") else ""}'
                           f'{"no audio" if not c.get("audio") else ""}')
        line = (f'  {year} {artist}\n      sheet: {title}\n'
                f'      apple: {c.get("canon")}\n      used : {used}')
        if X.score_coll(c.get('canon'), title):
            if used != title:
                ok.append(line)
        elif (artist, used) in EXPECTED_SUSPECT:
            expected.append(f'  {year} {artist} - {used}  (apple: {c.get("canon")!r})')
        else:
            suspect.append(line)

    print(f'titles taken from Apple that differ from the sheet: {len(ok)}')
    for l in ok:
        print(l)
    print(f'\nknown multi-record rows (resolved against one half by design): {len(expected)}')
    for l in expected:
        print(l)
    print(f'\nSUSPECT - title does not answer to the album asked for: {len(suspect)}')
    for l in suspect:
        print(l)
    print(f'\nincomplete: {len(missing)}')
    for l in missing:
        print(l)


if __name__ == '__main__':
    main()
