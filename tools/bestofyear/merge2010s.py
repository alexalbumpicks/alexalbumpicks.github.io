#!/usr/bin/env python3
"""Fold the shard caches back into /tmp/cache2010s.json and report what's missing.

Where two workers resolved the same album (the slices overlap at the seams), the
record with more filled-in fields wins; a tie keeps the one already in the main cache.

Usage: python3 merge2010s.py
"""
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve2010s as T

MAIN = '/tmp/cache2010s.json'


def filled(rec):
    return sum(1 for f in ('art', 'audio', 'track', 'canon') if rec.get(f))


def main():
    cache = json.load(open(MAIN)) if os.path.exists(MAIN) else {}
    added = 0
    for path in sorted(glob.glob('/tmp/cache2010s_*.json')):
        for k, v in json.load(open(path)).items():
            if k not in cache or filled(v) > filled(cache[k]):
                cache[k] = v
                added += 1
    json.dump(cache, open(MAIN, 'w'), indent=1, ensure_ascii=False)

    todo = T.targets()
    missing = [t for t in todo if f'{t[0]}|{t[2]}|{t[1]}' not in cache]
    have = [cache[f'{t[0]}|{t[2]}|{t[1]}'] for t in todo
            if f'{t[0]}|{t[2]}|{t[1]}' in cache]
    print(f'merged {added} records; cache now {len(cache)}')
    print(f'resolved {len(have)}/{len(todo)}   still to do: {len(missing)}')
    print(f'  art  : {sum(1 for r in have if r.get("art"))}/{len(have)}')
    print(f'  audio: {sum(1 for r in have if r.get("audio"))}/{len(have)}')
    gaps = [r for r in have if not (r.get('art') and r.get('audio'))]
    if gaps:
        print('\ngaps:')
        for r in sorted(gaps, key=lambda r: r['year']):
            print(f'  {r["year"]} {r["artist"]} - {r["album"]}  '
                  f'[{"art" if r.get("art") else "NO ART"}, '
                  f'{"audio" if r.get("audio") else "NO AUDIO"}]  {",".join(r.get("notes") or [])}')
    if missing:
        print('\nnot yet resolved:')
        for y, alb, act in missing:
            print(f'  {y} {act} - {alb}')


if __name__ == '__main__':
    main()
