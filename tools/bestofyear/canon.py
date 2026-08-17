#!/usr/bin/env python3
"""Resolve the canonical album title for each cached import via the iTunes catalogue.

The spreadsheet's casing is inconsistent ("Up the bracket", "Turn on the bright
lights") and it carries outright typos. Apple's collectionName is used as the
canonical spelling, but only when it's confidently the same record - the base title
must match after stripping parentheticals, accents and punctuation.

Writes `canon` into the existing cache entries. Idempotent and resumable.

Usage: python3 canon.py [--cache PATH]
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

CACHE = '/tmp/cache2000s.json'
UA = {'User-Agent': 'Mozilla/5.0'}

REJECT = ('karaoke', 'tribute', 'in the style of', 'made popular by', 'instrumental',
          'originally performed', 'cover', 'lofi', 'music of')
SUFFIX = re.compile(
    r'\s*[\(\[](deluxe|bonus|expanded|remaster|anniversary|special|legacy|collector|'
    r'super deluxe|explicit|clean|edition|version|reissue|disc).*?[\)\]]\s*$', re.I)


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


def base(t):
    prev = None
    while prev != t:
        prev = t
        t = SUFFIX.sub('', t).strip()
    return t


def get(url, tries=3):
    for n in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(1.5 * (n + 1))


def canonical(artist, album):
    for term in (f'{artist} {album}', album):
        try:
            r = get('https://itunes.apple.com/search?' +
                    urllib.parse.urlencode({'term': term, 'entity': 'album', 'limit': 25}))
        except Exception:
            continue
        best = None
        for x in r.get('results', []):
            cn, an = x.get('collectionName') or '', x.get('artistName') or ''
            if not (norm(artist) in norm(an) or norm(an) in norm(artist)):
                continue
            if any(w in cn.lower() for w in REJECT):
                continue
            b = base(cn)
            # Only trust it when it's unmistakably the same record.
            if norm(b) != norm(album):
                continue
            # Prefer the plain edition over a "(Deluxe Edition)" listing.
            if best is None or len(cn) < len(best):
                best = b
        if best:
            return best
        time.sleep(0.25)
    return None


def main():
    path = CACHE
    if '--cache' in sys.argv:
        path = sys.argv[sys.argv.index('--cache') + 1]
    cache = json.load(open(path))
    todo = [k for k, v in cache.items() if 'canon' not in v]
    changed = 0
    for n, k in enumerate(todo, 1):
        v = cache[k]
        c = canonical(v['artist'], v['album'])
        v['canon'] = c
        if c and c != v['album']:
            changed += 1
            print(f"  {v['year']}  {v['artist']}\n      sheet: {v['album']}\n      apple: {c}")
        json.dump(cache, open(path, 'w'), indent=1, ensure_ascii=False)
        if n % 20 == 0:
            print(f'  ...{n}/{len(todo)}', flush=True)
    print(f'\nchecked {len(todo)}, {changed} titles differ from the sheet')


if __name__ == '__main__':
    main()
