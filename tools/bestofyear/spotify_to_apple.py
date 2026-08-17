#!/usr/bin/env python3
"""Swap Spotify track embeds for Apple 30-second previews.

Spotify's iframe embed won't autoplay, so the Listen button is a dead end; an Apple
preview URL renders as a native <audio> element that plays inline. Same song wherever
Apple has it.

Spotify's Web API is unusable on a free account (403 "Active premium subscription
required"), so the track name comes from the public oEmbed endpoint instead - it needs
no auth and returns the title directly.

Resolution order for each track:
  1. song search on "<artist> <track>", preferring a hit whose collection is the album
     the entry is already filed under
  2. failing that, look the album up and walk its tracklist - catches songs whose title
     Apple spells differently enough to miss a text search

Results are cached, so the run is resumable and re-runnable for free. Nothing is
written unless --apply is passed, and entries Apple can't match keep their Spotify URL.

Usage: python3 spotify_to_apple.py [--apply] [--limit N]
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data.js')
CACHE = '/tmp/apple_swap.json'
UA = {'User-Agent': 'indie-rock-timeline/1.0 (xavjiang@gmail.com)'}
STOREFRONTS = ['US', 'GB', 'JP', 'TW', 'FR', 'DE']


# Spotify tags reissues onto the track name ("Alone Again Or - 2015 Remaster") while
# Apple usually doesn't, so a literal compare misses. Strip the tag from both sides.
EDITION = re.compile(
    r'\s*[-–(\[]\s*((\d{4}\s*)?(digital\s*)?(remaster|remastered|re-?master)'
    r'|mono|stereo|single|album|radio|remix|deluxe|expanded|anniversary|bonus)'
    r'[^)\]]*[)\]]?\s*$', re.I)


def strip_edition(t):
    prev = None
    while prev != t:
        prev = t
        t = EDITION.sub('', t or '').strip()
    return t


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^\w]', '', s.lower(), flags=re.UNICODE)


def same_track(a, b):
    return norm(strip_edition(a)) == norm(strip_edition(b))


def get(url, tries=5):
    """iTunes answers 403 under even mild load, so back off generously."""
    for n in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            if n == tries - 1:
                return {}
            time.sleep(3 * (n + 1))


def spotify_track_name(url):
    r = get('https://open.spotify.com/oembed?' + urllib.parse.urlencode({'url': url}), tries=3)
    return r.get('title')


def by_song_search(artist, track, album):
    for country in STOREFRONTS:
        r = get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': f'{artist} {strip_edition(track)}', 'entity': 'song',
             'limit': 25, 'country': country}))
        hits = [x for x in r.get('results', []) if x.get('previewUrl')
                and same_track(x.get('trackName'), track)
                and (norm(artist) in norm(x.get('artistName'))
                     or norm(x.get('artistName')) in norm(artist))]
        # Prefer the pressing the entry is actually filed under, so a preview from a
        # greatest-hits comp doesn't quietly replace the album track.
        same_album = [x for x in hits
                      if norm(album) in norm(x.get('collectionName'))
                      or norm(x.get('collectionName')) in norm(album)]
        pick = (same_album or hits or [None])[0]
        if pick:
            return pick['previewUrl'], pick.get('collectionName'), country
        time.sleep(1.2)
    return None, None, None


def by_album_walk(artist, track, album):
    for country in STOREFRONTS:
        r = get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
            {'term': f'{artist} {album}', 'entity': 'album', 'limit': 15, 'country': country}))
        for alb in r.get('results', []):
            an, cn = alb.get('artistName') or '', alb.get('collectionName') or ''
            if not (norm(artist) in norm(an) or norm(an) in norm(artist)):
                continue
            if not (norm(album) in norm(cn) or norm(cn) in norm(album)):
                continue
            songs = get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
                {'id': alb['collectionId'], 'entity': 'song', 'limit': 80, 'country': country}))
            for x in songs.get('results', [])[1:]:
                if x.get('previewUrl') and same_track(x.get('trackName'), track):
                    return x['previewUrl'], cn, country
            time.sleep(1.0)
        time.sleep(1.2)
    return None, None, None


def load_entries():
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    return src, s, e, json.loads(src[s:e].rstrip().rstrip(';'))


def main():
    apply = '--apply' in sys.argv
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None

    src, s, e, entries = load_entries()
    targets = [x for x in entries if 'open.spotify.com' in (x.get('audio') or '')]
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = [x for x in targets if x['audio'] not in cache][:limit]
    print(f'{len(targets)} Spotify links, {len(cache)} already resolved, '
          f'{len(todo)} to do\n', flush=True)

    for n, x in enumerate(todo, 1):
        artist, album = x['artist'], x['title']
        track = spotify_track_name(x['audio'])
        rec = {'year': x['year'], 'artist': artist, 'album': album,
               'track': track, 'audio': None, 'via': None}
        if track:
            url, coll, country = by_song_search(artist, track, album)
            if not url:
                url, coll, country = by_album_walk(artist, track, album)
            if url:
                rec.update(audio=url, via=f'{coll} [{country}]')
        cache[x['audio']] = rec
        json.dump(cache, open(CACHE, 'w'), indent=1, ensure_ascii=False)
        mark = 'ok  ' if rec['audio'] else 'MISS'
        print(f"[{n}/{len(todo)}] {mark} {x['year']} {artist} - {album}"
              f"  :: {track or '(no spotify title)'}"
              f"{'  <- ' + rec['via'] if rec['via'] else ''}", flush=True)
        time.sleep(0.8)

    resolved = {k: v for k, v in cache.items() if v.get('audio')}
    print(f'\nresolved {len(resolved)}/{len(targets)}')
    misses = [v for k, v in cache.items() if not v.get('audio')]
    if misses:
        print('\nno Apple preview - keeping the Spotify embed:')
        for v in misses:
            print(f"  {v['year']} {v['artist']} - {v['album']}  :: {v['track']}")

    if not apply:
        print('\ndry run - rerun with --apply to write data.js')
        return

    src, s, e, entries = load_entries()
    n = 0
    for x in entries:
        hit = resolved.get(x.get('audio') or '')
        if hit:
            x['audio'] = hit['audio']
            n += 1
    open(DATA, 'w').write(
        src[:s] + json.dumps(entries, indent=2, ensure_ascii=False) + src[e:])
    print(f'\nswapped {n} entries to Apple previews')


if __name__ == '__main__':
    main()
