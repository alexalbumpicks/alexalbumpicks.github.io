#!/usr/bin/env python3
"""Append the 2010s Best-of-Year import to bestof-data.js and assign yearRank.

Same conventions as build2000s.py (see memory/project_bestofyear_import.md), with
the post-fork differences:
  - writes bestof-data.js / BEST_OF_ENTRIES, not data.js / ENTRIES
  - no `era`, `movement`, `bestOfYearOnly` or `hideFromBestOfYear` fields - which
    view an album appears in is decided by the file it lives in
  - Genre + Sub-genre become tags
  - curated entries are NEVER overwritten; they receive yearRank, plus tags only
    if they have none

Unlike the 2000s, yearRank here is simply the sheet's row order rather than a
score-descending sort - Alex is re-ranking these by hand, so the import only needs to
put them in a stable, predictable order to start from. (The sheet is already roughly
score-ordered within each year, so the two barely differ.) Score still sets `rating`,
and is still never stored.

Ranks are assigned to *every* album in the year, including ones the sheet doesn't
list: best-of-year.js only honours yearRank when all of them have one.

Usage: python3 build2010s.py [--apply]
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boy
from sheet import records, fixed, fixed_year, sheet_year
from build2000s import best_title, rating_from_score, tags_for
import gapfill2010s

CACHE = '/tmp/cache2010s.json'
GAP = '/tmp/gapfill2010s.json'
YEARS = range(2010, 2020)

norm = boy.norm

# Sheet spellings that differ from the ones already in bestof-data.js. Confirmed to
# be the same record; the bestof-data.js spelling wins so the album isn't double-listed.
ALIASES = {}


def title_for(sheet_title, canon):
    """The title to file the album under.

    Apple's spelling is worth taking when it names the same record - channel ORANGE,
    E•MO•TION, BEYONCÉ, Bon Iver, Bon Iver. It isn't when Apple only matched by carrying
    something extra: the album is Teen Dream, not "Teen Dream (Bonus Track Version)", and
    II, not "II (10 Year Anniversary Edition)". Nor is it worth taking when Apple has
    bowdlerised it - the record is Norman Fucking Rockwell!, whatever the store calls it.
    """
    if not canon or '*' in canon or gapfill2010s.score_coll(canon, sheet_title) < 6:
        return sheet_title
    # A parenthetical the sheet doesn't have is an edition marker, not part of the name:
    # score_coll matches on the base title, so "Teen Dream (Bonus Track Version)" scores
    # a full 6. Take Apple's casing, drop its packaging.
    if boy.norm(canon) != boy.norm(sheet_title):
        canon = re.sub(r'\s*[\(\[].*?[\)\]]\s*$', '', canon).strip() or canon
    return best_title(sheet_title, canon)


def main():
    apply = '--apply' in sys.argv
    src, s, e, entries = boy.load()
    cache = json.load(open(CACHE))
    gap = json.load(open(GAP)) if os.path.exists(GAP) else {}
    recs, _ = records()

    by_key = {}
    for x in entries:
        if x.get('type') == 'album':
            by_key.setdefault((norm(x.get('title')), norm(x.get('artist'))), []).append(x)

    new_entries, rank_updates, tag_updates, problems = [], [], [], []

    for year in YEARS:
        pool = []  # (not_in_sheet, order, payload)
        used = set()

        # Rows land in the year YEAR_FIX says they belong to. A row moved in from
        # another year has no place in this year's running order, so it's pushed past
        # the native rows rather than interleaved at whatever index it happened to hold.
        rows = []
        for i, r in enumerate(recs):
            if not r.get('Year') or fixed_year(r) != year:
                continue
            moved = sheet_year(r) != year
            rows.append((1 if moved else 0, i, r))
        rows.sort(key=lambda t: (t[0], t[1]))

        for order, (_, _, r) in enumerate(rows):
            title, artist = fixed(r)
            alias = ALIASES.get((r['Act'], r['Albums']))
            raw = (r.get('Score') or '').strip()
            if raw.replace('.', '', 1).isdigit():
                score = float(raw)
            else:
                # Only affects `rating` now that order comes from the sheet, so an
                # unscored row keeps its place and just lands on the default 3 stars.
                score = float('-inf')
                problems.append(f'  NO SCORE {year} {r["Act"]} - {title} '
                                f'(sheet says {raw!r}) - rating 3')

            # Match on the corrected spelling as well as the sheet's, so a row the
            # fix tables rename doesn't duplicate an album that's already here.
            match = (by_key.get((norm(alias or r['Albums']), norm(r['Act'])))
                     or by_key.get((norm(title), norm(artist))))
            if match:
                same = [x for x in match if x.get('year') == year]
                if not same:
                    problems.append(f'  year mismatch: sheet {year} vs bestof-data.js '
                                    f'{match[0].get("year")}  {r["Act"]} - {r["Albums"]}')
                    continue
                for x in same:
                    used.add(id(x))
                    pool.append((0, order, ('existing', x)))
                    if not x.get('tags'):
                        tag_updates.append((x, tags_for(r)))
                continue

            # Keyed on the sheet's own year, which is what the resolvers cached under.
            ck = f'{sheet_year(r)}|{r["Act"]}|{r["Albums"]}'
            c = dict(cache.get(ck) or {})
            g = gap.get(ck)
            if g:  # second-pass results win: they were resolved with stricter matching
                for f in ('art', 'audio', 'track'):
                    if g.get(f):
                        c[f] = g[f]
                # canon is taken even when it's None. The second pass only looks at a
                # record when the first one came back wrong or incomplete, so a cached
                # title it declined to confirm is one to drop, not to fall back on.
                c['canon'] = g.get('canon')
            title = title_for(title, c.get('canon'))
            if not c.get('art'):
                problems.append(f'  NO ART   {year} {artist} - {title}')
            if not c.get('audio'):
                problems.append(f'  NO AUDIO {year} {artist} - {title}')
            pool.append((0, order, ('new', {
                'type': 'album',
                'year': year,
                'title': title,
                'artist': artist,
                'tagline': '',
                'art': c.get('art') or '',
                'audio': c.get('audio') or '',
                'tier': '',
                'artBg': '#181818',
                'artColor': '#999',
                'rating': rating_from_score(score),
                'tags': tags_for(r),
                'review': '',
                'context': '',
                'tracks': [],
            })))

        # Albums already filed under this year that the sheet doesn't list. They have
        # no row order to inherit, so they go after the sheet's rows in file order.
        for order, x in enumerate(entries):
            if (x.get('type') == 'album' and x.get('year') == year
                    and id(x) not in used):
                pool.append((1, order, ('existing', x)))

        pool.sort(key=lambda p: (p[0], p[1]))
        for rank, (_, _, (kind, payload)) in enumerate(pool, 1):
            if kind == 'new':
                payload['yearRank'] = rank
                new_entries.append(payload)
            else:
                rank_updates.append((payload, rank))

    print(f'new entries      : {len(new_entries)}')
    print(f'yearRank updates : {len(rank_updates)} existing entries')
    print(f'tags backfilled  : {len(tag_updates)} existing entries')
    print(f'with art         : {sum(1 for x in new_entries if x["art"])}/{len(new_entries)}')
    print(f'with audio       : {sum(1 for x in new_entries if x["audio"])}/{len(new_entries)}')
    if problems:
        print('\nissues:')
        for p in problems:
            print(p)

    if not apply:
        print('\ndry run - rerun with --apply to write bestof-data.js')
        return

    for x, rank in rank_updates:
        x['yearRank'] = rank
    for x, tags in tag_updates:
        x['tags'] = tags
    entries.extend(new_entries)
    boy.save(src, s, e, entries)
    print(f'\nwrote {len(new_entries)} new entries to bestof-data.js')


if __name__ == '__main__':
    main()
