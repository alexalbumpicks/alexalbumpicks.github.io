#!/usr/bin/env python3
"""Append the 2020s Best-of-Year import (2020-2024) to bestof-data.js.

Same conventions as build2010s.py - see memory/project_bestofyear_import.md:
  - writes bestof-data.js / BEST_OF_ENTRIES
  - Genre + Sub-genre become tags; Score sets `rating` and is never stored
  - yearRank is the sheet's row order, not a score sort: Alex re-ranks by hand, so the
    import only has to be stable and predictable
  - curated entries are NEVER overwritten; they receive yearRank, plus tags if they have none

The only structural difference from 2010s is that there is one cache, not a cache plus a
gapfill overlay - resolve2020s.py does a single catalogue-first pass - so there is no
merge step and no rule about which pass wins.

Usage: python3 build2020s.py [--set NAME] [--apply]
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# `sheet` and `gapfill` first - resolve2000s puts /tmp on the path ahead of us and stale
# copies of both live there. Importing ours pins them in sys.modules for everyone.
# gapfill is on this list because score2020s calls G.amp, which the /tmp copy predates:
# without the pin the build dies on AttributeError while the resolver, which happens to
# import gapfill early, runs fine.
import importset
from sheet import records, fixed, fixed_year, sheet_year
import gapfill  # noqa: F401  - imported for the sys.modules pin, not used directly
import boy
from build2000s import best_title, rating_from_score, tags_for
import score2020s

YEARS, CACHE = importset.pick()
APPEND = importset.append_only()

norm = boy.norm

# Sheet spellings that differ from ones already in bestof-data.js. Confirmed the same
# record; the bestof-data.js spelling wins so the album isn't double-listed.
ALIASES = {}

# Albums where Apple's spelling of the *same words* is the worse one, so the sheet keeps it.
#
# Apple's casing is normally the reason to take canon at all - 'brat', 'folklore', 'ORQUÍDEAS'
# arrive correct for free. But its titles are machine-cased, and machine casing pads
# punctuation: 'Post-Nothing' comes back as 'Post - Nothing'. That norms identically to the
# sheet, so it is provably the same record and purely a question of orthography - which the
# sheet gets right and Apple does not.
#
# Keyed by (artist, sheet title). Only for norm-equal pairs; anything where Apple genuinely
# names a different edition belongs in APPLE_ID or ALIASES instead. Interior capitalisation
# is the other half of this and is handled by rule - see _only_smallword_caps.
KEEP_SHEET_TITLE = {
    ('Japandroids', 'Post-Nothing'),     # apple: 'Post - Nothing'
    # apple: 'American Football (Lp4)'. The band numbers its self-titled records LP1..LP4 in
    # capitals; Apple's title-caser sees an ordinary word and writes 'Lp4'. Norm-equal, so this
    # is only orthography - and _only_smallword_caps cannot catch it, since 'lp4' is not a
    # small word but a initialism the rule has no way to know about.
    ('American Football', 'American Football LP4'),
}

# Words English title case leaves lowercase inside a title. Apple's does not.
SMALL_WORDS = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from', 'in', 'nor', 'of',
               'on', 'or', 'the', 'to', 'with'}


def _only_smallword_caps(sheet_title, canon):
    """True if canon is the sheet's title with interior small words capitalised.

    Apple returned 'Ride The Tiger', 'Wolf Songs For Lambs' and 'Boys For Pele' for rows the
    sheet had already spelled correctly - three in one import, so this is the house style of
    Apple's metadata rather than a run of bad luck, and listing them by hand would mean
    catching each new one in the audit forever.

    Deliberately narrow. Every word must match case-insensitively, so this can never fire on
    two different titles; only small words may differ, so 'brat' -> 'BRAT' still takes Apple's;
    and the first word is exempt, because a title legitimately opens on a capitalised 'The'.
    """
    a, b = sheet_title.split(), canon.split()
    if len(a) != len(b):
        return False
    found = False
    for i, (w, c) in enumerate(zip(a, b)):
        if w == c:
            continue
        if w.lower() != c.lower():
            return False                      # a genuinely different word
        if i == 0 or w.lower() not in SMALL_WORDS:
            return False                      # not the pattern this is for
        if not (w.islower() and c[:1].isupper()):
            return False                      # sheet is the one shouting, not Apple
        found = True
    return found


def title_for(sheet_title, canon, artist=None):
    """The title to file the album under.

    Apple's spelling is worth taking when it names the same record - 'brat', 'folklore',
    'ORQUÍDEAS', 'Seed of a Seed' all come back correctly cased for free. It isn't worth
    taking when Apple only matched by carrying something extra ('In Waves (Deluxe)'), and
    it isn't when Apple has bowdlerised the name.

    The three rows that stand for two records - songs / instrumentals, Piedras 1 & 2,
    KiCk i-v - resolve against one half of the pair, so canon names only that half and
    scores 0. They keep the sheet's title, which is the point.
    """
    if not canon or '*' in canon or score2020s.score_coll(canon, sheet_title) < 6:
        return sheet_title
    if (artist, sheet_title) in KEEP_SHEET_TITLE:
        return sheet_title
    if _only_smallword_caps(sheet_title, canon):
        return sheet_title
    if boy.norm(canon) != boy.norm(sheet_title):
        canon = re.sub(r'\s*[\(\[].*?[\)\]]\s*$', '', canon).strip() or canon
    return best_title(sheet_title, canon)


def main():
    apply = '--apply' in sys.argv
    src, s, e, entries = boy.load()
    cache = json.load(open(CACHE))
    recs, _ = records()

    by_key = {}
    for x in entries:
        if x.get('type') == 'album':
            by_key.setdefault((norm(x.get('title')), norm(x.get('artist'))), []).append(x)

    new_entries, rank_updates, tag_updates, problems = [], [], [], []

    for year in YEARS:
        pool = []  # (not_in_sheet, order, payload)
        used = set()

        rows = []
        # The sheet lists some records twice - usually because a row was re-typed under a
        # corrected year and the original left in place, which YEAR_FIX then folds back onto
        # the same year (Lorde's Virgin is filed 2024 and 2025). Neither copy matches anything
        # written yet, so without this both get appended and the duplicate is only visible
        # afterwards. That is where the '2026 Artist - New Album' pair came from.
        seen_rows = set()
        for i, r in enumerate(recs):
            if not r.get('Year') or fixed_year(r) != year:
                continue
            t, a = fixed(r)
            k = (norm(t), norm(a))
            if k in seen_rows:
                problems.append(f'  DUPLICATE ROW {year} {r["Act"]} - {r["Albums"]} '
                                f'(already taken from an earlier row; skipped)')
                continue
            seen_rows.add(k)
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
                score = float('-inf')
                problems.append(f'  NO SCORE {year} {r["Act"]} - {title} '
                                f'(sheet says {raw!r}) - rating 3')

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

            ck = f'{sheet_year(r)}|{r["Act"]}|{r["Albums"]}'
            c = cache.get(ck) or {}
            title = title_for(title, c.get('canon'), artist)
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

        for order, x in enumerate(entries):
            if (x.get('type') == 'album' and x.get('year') == year
                    and id(x) not in used):
                pool.append((1, order, ('existing', x)))

        pool.sort(key=lambda p: (p[0], p[1]))

        if APPEND:
            # The year is already on the site and already ordered, so the running order is not
            # ours to rewrite - see importset.APPEND_ONLY. Existing entries keep the rank they
            # have (they are not added to rank_updates at all) and the new albums go on the end
            # in sheet order.
            #
            # Counting from the year's current maximum is what makes this safe against a save
            # that has been re-ranked by hand. Re-ranking permutes 1..N, so it cannot change N:
            # a new album numbered N+1 clears every rank in the baked file *and* every rank in
            # anyone's localStorage, without either having to know about the other.
            top = max(((x.get('yearRank') or 0) for x in entries
                       if x.get('type') == 'album' and x.get('year') == year), default=0)
            for _, _, (kind, payload) in pool:
                if kind != 'new':
                    continue
                top += 1
                payload['yearRank'] = top
                new_entries.append(payload)
        else:
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
