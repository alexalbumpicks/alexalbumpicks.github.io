#!/usr/bin/env python3
"""Append the 2000s Best-of-Year import to data.js and assign yearRank.

Conventions (see memory/project_bestofyear_import.md):
  - imported rows become bestOfYearOnly entries so they stay off the main timeline
  - Score sets yearRank (descending); the raw score is never stored
  - Genre + Sub-genre become tags
  - existing curated entries are NEVER overwritten - they only receive yearRank

Curated albums absent from the sheet are interleaved by star rating, because
best-of-year.js only honours yearRank when *every* album in the year has one.

Usage: python3 build2000s.py [--apply]
"""
import json, re, sys, unicodedata

sys.path.insert(0, '/tmp')
from sheet import records, fixed

CJK = re.compile(r'[぀-ヿ㐀-鿿]')


def best_title(sheet_title, canon):
    """Apple's spelling wins over the sheet's inconsistent casing and typos.

    Skipped for CJK titles: Apple lists 华丽的冒险 under its traditional-Chinese
    name, which would leave a traditional title next to a simplified artist.
    """
    if not canon or canon == sheet_title:
        return sheet_title
    if CJK.search(sheet_title) or CJK.search(canon):
        return sheet_title
    return canon

DATA = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/data.js'
CACHE = '/tmp/cache2000s.json'
YEARS = [y for y in range(2000, 2010) if y != 2002]  # 2002 already imported

ERA_FOR_YEAR = {
    2000: 'era_1776565014692',  # Chaos before the arrival of a new sound (1999-2001)
    2001: 'era_1776565014692',
    2003: 'era_1776471732213',  # Post-Punk Revival (2001-2003)
    2004: 'era_1776446456442',  # Folk Rock Goes Chamber (2003-2005)
    2005: 'era_1776446456442',
    2006: 'sleaze',             # Indie Sleaze: Stage I (2006-2009)
    2007: 'sleaze',
    2008: 'sleaze',
    2009: 'sleaze',
}

# The sheet spells some albums differently from data.js, so a plain normalized
# compare treats them as new and silently duplicates a curated entry. These are all
# confirmed to be the same record - the data.js spelling is the one that wins.
ALIASES = {
    ('Animal Collective', 'Merriweather Post Pavillion'): 'Merriweather Post Pavilion',
    ('Blonde Redhead', '23.0'): '23',
    ('Wolf Parade', 'Apologies to Queen Mary'): 'Apologies to the Queen Mary',
    ('Iron & Wine', 'Our Endlessly Numbered Days'): 'Our Endless Numbered Days',
    ('Sweet Trip', 'Velocity : Design : Comfort'): 'Velocity : Design : Comfort',
    ('Songs: Ohia', 'The Magnolia Electric co.'): 'The Magnolia Electric Co.',
    ('The Microphones', 'The Glow, Part 2'): 'The Glow, Pt. 2',
}

# A curated album with no sheet score still needs a rank; map its stars onto the
# sheet's 5-10 scale so it lands among comparable records.
RATING_AS_SCORE = {5: 9.5, 4: 8.5, 3: 7.5, 2: 6.5, 1: 5.5}


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


def rating_from_score(sc):
    if sc == float('-inf'):
        return 3  # unscored in the sheet
    return 5 if sc >= 9.5 else 4 if sc >= 8.5 else 3 if sc >= 7.5 else 2 if sc >= 6.5 else 1


def tags_for(rec):
    out = []
    for field in ('Genre', 'Sub-genre'):
        for t in (rec.get(field) or '').split(','):
            t = t.strip()
            if t and t not in out:
                out.append(t)
    return out


def load_entries():
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    return src, s, e, json.loads(src[s:e].rstrip().rstrip(';'))


def main():
    apply = '--apply' in sys.argv
    src, s, e, entries = load_entries()
    cache = json.load(open(CACHE))
    recs, _ = records()

    by_key = {}
    for x in entries:
        if x.get('type') == 'album':
            by_key.setdefault((norm(x.get('title')), norm(x.get('artist'))), []).append(x)

    new_entries, rank_updates, problems = [], [], []

    for year in YEARS:
        pool = []  # (score, is_curated, order, payload)
        used = set()

        rows = [r for r in recs if r.get('Year') and int(float(r['Year'])) == year]
        for order, r in enumerate(rows):
            title, artist = fixed(r)
            alias = ALIASES.get((r['Act'], r['Albums']))
            key = (norm(alias or r['Albums']), norm(r['Act']))
            raw = (r.get('Score') or '').strip()
            if raw.replace('.', '', 1).isdigit():
                score = float(raw)
            else:
                # Scott Walker's "The Drift" is scored "???" in the sheet. Sort it
                # last in its year rather than inventing a score.
                score = float('-inf')
                problems.append(f'  NO SCORE {year} {r["Act"]} - {title} '
                                f'(sheet says {raw!r}) - ranked last, rating 3')
            match = by_key.get(key)
            if match:
                # Album already curated. Only rank it, and only if it's filed under
                # this year - a year mismatch is surfaced, never silently moved.
                same = [x for x in match if x.get('year') == year]
                if not same:
                    problems.append(f'  year mismatch: sheet {year} vs data.js '
                                    f'{match[0].get("year")}  {r["Act"]} - {r["Albums"]}')
                    continue
                for x in same:
                    if x.get('hideFromBestOfYear'):
                        continue
                    used.add(id(x))
                    pool.append((score, 0, order, ('existing', x)))
                continue

            # resolve2000s.py keys the cache on the raw sheet title, before TITLE_FIX.
            ck = f'{year}|{r["Act"]}|{r["Albums"]}'
            c = cache.get(ck) or {}
            title = best_title(title, c.get('canon'))
            if not c.get('art'):
                problems.append(f'  NO ART  {year} {r["Act"]} - {title}')
            if not c.get('audio'):
                problems.append(f'  NO AUDIO {year} {r["Act"]} - {title}')
            pool.append((score, 0, order, ('new', {
                'type': 'album',
                'era': ERA_FOR_YEAR[year],
                'year': year,
                'title': title,
                'artist': artist,
                'tagline': '',
                'art': c.get('art') or '',
                'audio': c.get('audio') or '',
                'tier': '',
                'movement': '',
                'artBg': '#181818',
                'artColor': '#999',
                'rating': rating_from_score(score),
                'tags': tags_for(r),
                'review': '',
                'context': '',
                'tracks': [],
                'bestOfYearOnly': True,
                'hideFromBestOfYear': False,
            })))

        # Curated albums this year that the sheet doesn't list.
        for order, x in enumerate(entries):
            if (x.get('type') == 'album' and x.get('year') == year
                    and not x.get('hideFromBestOfYear') and id(x) not in used):
                pool.append((RATING_AS_SCORE.get(x.get('rating'), 7.0), 1, order,
                             ('existing', x)))

        # Score descending; on a tie the sheet's own row order wins.
        pool.sort(key=lambda p: (-p[0], p[1], p[2]))
        for rank, (_, _, _, (kind, payload)) in enumerate(pool, 1):
            if kind == 'new':
                payload['yearRank'] = rank
                new_entries.append(payload)
            else:
                rank_updates.append((payload, rank))

    print(f'new entries      : {len(new_entries)}')
    print(f'yearRank updates : {len(rank_updates)} existing entries')
    print(f'with art         : {sum(1 for x in new_entries if x["art"])}/{len(new_entries)}')
    print(f'with audio       : {sum(1 for x in new_entries if x["audio"])}/{len(new_entries)}')
    if problems:
        print('\nissues:')
        for p in problems:
            print(p)

    if not apply:
        print('\ndry run - rerun with --apply to write data.js')
        return

    for x, rank in rank_updates:
        x['yearRank'] = rank
    entries.extend(new_entries)
    open(DATA, 'w').write(src[:s] + json.dumps(entries, indent=2, ensure_ascii=False) + src[e:])
    print(f'\nwrote {len(new_entries)} new entries to data.js')


if __name__ == '__main__':
    main()
