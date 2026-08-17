#!/usr/bin/env python3
"""Stamp every local css/js reference in the HTML with a hash of that file's contents.

Hand-maintained `?v=` strings drift: you change timeline.js, forget the stamp, and the
browser keeps serving the old file against a new data.js - which looks exactly like a
mysterious caching bug and wastes an hour. A content hash can't drift, because it *is*
the content: it changes when and only when the file changes, so re-running this is
always safe and never busts a cache unnecessarily.

Usage:
  python3 tools/stamp.py            # show what would change
  python3 tools/stamp.py --apply
"""
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['index.html', 'best-of-year.html']

# src="foo.js?v=abc"  /  href="foo.css?v=abc"  - local files only, never CDN URLs.
REF = re.compile(r'(?P<attr>\b(?:src|href)=")(?P<file>[\w./-]+\.(?:js|css))(?:\?v=[^"]*)?(?P<end>")')


def digest(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:10]


def main():
    apply = '--apply' in sys.argv
    changed = 0

    for page in PAGES:
        page_path = os.path.join(ROOT, page)
        if not os.path.exists(page_path):
            print(f'{page}: missing, skipped')
            continue
        src = open(page_path, encoding='utf-8').read()
        hits = []

        def sub(m):
            nonlocal changed
            target = os.path.join(ROOT, m.group('file'))
            if not os.path.exists(target):
                hits.append((m.group('file'), None, 'FILE NOT FOUND'))
                return m.group(0)
            new = digest(target)
            old_match = re.search(r'\?v=([^"]*)', m.group(0))
            old = old_match.group(1) if old_match else None
            if old != new:
                changed += 1
                hits.append((m.group('file'), old, new))
            else:
                hits.append((m.group('file'), old, None))
            return f"{m.group('attr')}{m.group('file')}?v={new}{m.group('end')}"

        out = REF.sub(sub, src)

        print(f'\n{page}')
        for name, old, new in hits:
            if new == 'FILE NOT FOUND':
                print(f'  !! {name:20} referenced but not on disk')
            elif new is None:
                print(f'     {name:20} unchanged ({old})')
            else:
                print(f'  -> {name:20} {old} -> {new}')

        if apply and out != src:
            open(page_path, 'w', encoding='utf-8').write(out)

    print(f'\n{changed} stamp(s) {"updated" if apply else "would change"}')
    if not apply and changed:
        print('dry run - rerun with --apply')


if __name__ == '__main__':
    main()
