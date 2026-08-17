#!/usr/bin/env python3
"""Probe iTunes / Deezer for the albums the bulk resolver failed on.

Read-only: prints candidates so each gap can be closed deliberately rather than by
another round of fuzzy matching that already missed once.

Usage:
  python3 probe.py itunes "search term" [album|song]
  python3 probe.py deezer "search term"
  python3 probe.py tracks <itunes_collection_id>
  python3 probe.py dztracks <deezer_album_id>
  python3 probe.py top "artist name"
"""
import json, sys, time, urllib.parse, urllib.request

UA = {'User-Agent': 'indie-rock-timeline/1.0 (xavjiang@gmail.com)'}


def get(url, tries=4):
    for n in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception as ex:
            if n == tries - 1:
                print(f'  !! {type(ex).__name__}: {ex}')
                return {}
            time.sleep(2 * (n + 1))


def main():
    mode, term = sys.argv[1], sys.argv[2]

    if mode == 'itunes':
        entity = sys.argv[3] if len(sys.argv) > 3 else 'album'
        r = get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': term, 'entity': entity, 'limit': 15}))
        for x in r.get('results', []):
            if entity == 'album':
                print(f"{x.get('collectionId')}  {x.get('artistName')} - {x.get('collectionName')}"
                      f"  [{(x.get('releaseDate') or '')[:4]}, {x.get('trackCount')}tr]")
            else:
                print(f"{x.get('collectionId')}  {x.get('artistName')} - {x.get('trackName')} "
                      f"({x.get('collectionName')})  "
                      f"{'PREVIEW' if x.get('previewUrl') else 'no-preview'}")

    elif mode == 'tracks':
        r = get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
            {'id': term, 'entity': 'song', 'limit': 60}))
        for x in r.get('results', [])[1:]:
            print(f"{x.get('trackNumber'):>3}  {x.get('trackName')}  "
                  f"{'PREVIEW' if x.get('previewUrl') else 'NONE'}")

    elif mode == 'deezer':
        r = get('https://api.deezer.com/search/album?' + urllib.parse.urlencode(
            {'q': term, 'limit': 15}))
        for x in r.get('data', []):
            print(f"{x.get('id')}  {(x.get('artist') or {}).get('name')} - {x.get('title')}"
                  f"  [{x.get('nb_tracks')}tr]")

    elif mode == 'dztracks':
        r = get(f'https://api.deezer.com/album/{term}/tracks?limit=200')
        for x in sorted(r.get('data', []), key=lambda t: -(t.get('rank') or 0)):
            print(f"{x.get('rank'):>7}  {x.get('title')}")

    elif mode == 'top':
        a = get('https://api.deezer.com/search/artist?' + urllib.parse.urlencode(
            {'q': term, 'limit': 3}))
        for art in a.get('data', []):
            print(f"--- {art['name']} ({art['id']})")
            t = get(f"https://api.deezer.com/artist/{art['id']}/top?limit=30")
            for x in t.get('data', []):
                print(f"  {x.get('rank'):>7}  {x.get('title')}  "
                      f"({(x.get('album') or {}).get('title')})")


if __name__ == '__main__':
    main()
