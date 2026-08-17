#!/usr/bin/env python3
"""Post-import verification for the 2000s Best-of-Year rows.

Checks four things that would each silently break the page:
  1. every art and audio URL actually returns 200
  2. every audio URL ends in an extension best-of-year.js will turn into an <audio>
     element - anything else renders as a dead link
  3. each year's yearRank values are exactly 1..N with no gaps or duplicates
  4. no two album entries share a (year, title, artist) identity

Usage: python3 verify.py
"""
import json, re, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
import urllib.request

DATA = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/data.js'
UA = {'User-Agent': 'Mozilla/5.0'}
# Mirrors audioEmbedHtml() in best-of-year.js. Anything matching one of these renders
# as a real player or a labelled link; anything else degrades to a bare "Open link".
HANDLED = [
    re.compile(r'open\.spotify\.com/(track|album|playlist|episode)/[A-Za-z0-9]+'),
    re.compile(r'(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]+'),
    re.compile(r'soundcloud\.com'),
    re.compile(r'\.(mp3|ogg|wav|m4a|aac|flac)(\?|$)', re.I),
]


def status(url):
    for method in ('HEAD', 'GET'):
        try:
            r = urllib.request.urlopen(
                urllib.request.Request(url, method=method, headers=UA), timeout=25)
            return r.status
        except Exception as ex:
            code = getattr(ex, 'code', None)
            if code and method == 'GET':
                return code
    return 'ERR'


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^\w]', '', s.lower(), flags=re.UNICODE)


def main():
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    entries = json.loads(src[s:e].rstrip().rstrip(';'))
    albums = [x for x in entries if x.get('type') == 'album']
    scope = [x for x in albums if 2000 <= (x.get('year') or 0) <= 2009]
    print(f'{len(entries)} entries, {len(albums)} albums, {len(scope)} in 2000-2009\n')

    # --- 2. extension check (free, do it before spending network time)
    bad_ext = [x for x in scope if x.get('audio')
               and not any(p.search(x['audio']) for p in HANDLED)]
    print(f'audio URLs best-of-year.js cannot embed: {len(bad_ext)}')
    for x in bad_ext:
        print(f'  {x["year"]} {x["artist"]} - {x["title"]}: {x["audio"]}')

    # --- 3. rank contiguity
    print('\nyearRank:')
    for year in range(2000, 2010):
        ys = [x for x in albums
              if x.get('year') == year and not x.get('hideFromBestOfYear')]
        ranks = sorted(x.get('yearRank') for x in ys)
        ok = ranks == list(range(1, len(ys) + 1))
        print(f'  {year}: {len(ys):>2} albums  {"OK" if ok else f"BROKEN {ranks}"}')

    # --- 4. duplicate identity
    seen = {}
    dupes = []
    for x in albums:
        k = (x.get('year'), norm(x.get('title')), norm(x.get('artist')))
        if k in seen:
            dupes.append((seen[k], x))
        seen[k] = x
    print(f'\nduplicate (year,title,artist): {len(dupes)}')
    for a, b in dupes:
        print(f'  {a["year"]} {a["artist"]} - {a["title"]}  ==  {b["artist"]} - {b["title"]}')

    # --- 1. reachability
    urls = {}
    for x in scope:
        for field in ('art', 'audio'):
            if x.get(field):
                urls.setdefault(x[field], []).append((field, x))
    print(f'\nchecking {len(urls)} URLs...')
    with ThreadPoolExecutor(max_workers=12) as pool:
        codes = dict(zip(urls, pool.map(status, urls)))
    bad = {u: c for u, c in codes.items() if c != 200}
    print(f'non-200: {len(bad)}')
    for u, c in bad.items():
        field, x = urls[u][0]
        print(f'  [{c}] {x["year"]} {x["artist"]} - {x["title"]} ({field})\n      {u}')

    fail = bool(bad_ext or dupes or bad)
    print('\n' + ('FAILURES ABOVE' if fail else 'all checks passed'))
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
