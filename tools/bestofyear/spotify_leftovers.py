#!/usr/bin/env python3
"""The six Spotify links spotify_to_apple.py couldn't convert.

Each failed for a reason worth naming, and three of them are actually data bugs:

  - The Cleaners from Venus, Fleeting Joys and Drop Nineteens have `artist` and `title`
    swapped in data.js, so every lookup searched for the album as if it were the band.
    Apple finds all three instantly once the fields are the right way round.
  - Anohni and the Johnsons: Apple credits I Am a Bird Now to "Antony and the Johnsons
    & ANOHNI", which neither contains nor is contained by the entry's artist string, so
    the substring artist gate rejected a correct match.
  - The Modern Lovers: Spotify's track is "Roadrunner (Alternative Version)"; the album
    track is plain "Roadrunner". Alex said the same song is fine, so take the album cut.
  - Vampire Weekend: the self-titled debut is missing from Apple's *US* search index
    entirely (every other VW record is there), so the album is pinned by collection ID
    against the GB storefront. Preview URLs are durable regardless of storefront.

Collection IDs are resolved at run time but the artist/track pairs are pinned, because
this is exactly the set where fuzzy matching already proved unreliable.

Usage: python3 spotify_leftovers.py [--apply]
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data.js')
UA = {'User-Agent': 'indie-rock-timeline/1.0 (xavjiang@gmail.com)'}

# (year, artist, title) -> corrected (artist, title). data.js has these reversed.
SWAPPED = {
    (1982, 'Midnight Cleaners', 'The Cleaners from Venus'):
        ('The Cleaners from Venus', 'Midnight Cleaners'),
    (2006, 'Despondent Transponder', 'Fleeting Joys'):
        ('Fleeting Joys', 'Despondent Transponder'),
    (1992, 'Delaware', 'Drop Nineteens'):
        ('Drop Nineteens', 'Delaware'),
}

# (year, artist, title) after the swap fix -> (apple search term, exact track name)
WANTED = {
    (1976, 'The Modern Lovers', 'The Modern Lovers'):
        ('Jonathan Richman & The Modern Lovers The Modern Lovers', 'Roadrunner'),
    (1982, 'The Cleaners from Venus', 'Midnight Cleaners'):
        ('The Cleaners From Venus Midnight Cleaners', 'Only a Shadow'),
    (2005, 'Anohni and the Johnsons', 'I Am a Bird Now'):
        ('Antony and the Johnsons I Am a Bird Now', 'Fistful of Love'),
    (2006, 'Fleeting Joys', 'Despondent Transponder'):
        ('Fleeting Joys Despondent Transponder', 'Magnificent Oblivion'),
    # (collection ID, storefront) instead of a search term - see the note above.
    (2008, 'Vampire Weekend', 'Vampire Weekend'):
        ((271489741, 'GB'), 'Oxford Comma'),
    (1992, 'Drop Nineteens', 'Delaware'):
        ('Drop Nineteens Delaware', 'Kick the Tragedy'),
}


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^\w]', '', s.lower(), flags=re.UNICODE)


def get(url, tries=5):
    for n in range(tries):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception:
            if n == tries - 1:
                return {}
            time.sleep(3 * (n + 1))


def track_from_collection(cid, track, country='US'):
    songs = get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
        {'id': cid, 'entity': 'song', 'limit': 80, 'country': country}))
    res = songs.get('results', [])
    for x in res[1:]:
        if x.get('previewUrl') and norm(x.get('trackName')) == norm(track):
            return x['previewUrl'], res[0].get('collectionName')
    return None, None


def preview(term, album, track):
    """Find the album, then take the named track off its own tracklist."""
    if isinstance(term, tuple):
        return track_from_collection(term[0], track, term[1])
    r = get('https://itunes.apple.com/search?' + urllib.parse.urlencode(
        {'term': term, 'entity': 'album', 'limit': 20}))
    for alb in r.get('results', []):
        cn = alb.get('collectionName') or ''
        # Guard against "<album> - Single" and tribute/lullaby records.
        if norm(cn) != norm(album):
            continue
        songs = get('https://itunes.apple.com/lookup?' + urllib.parse.urlencode(
            {'id': alb['collectionId'], 'entity': 'song', 'limit': 80}))
        for x in songs.get('results', [])[1:]:
            if x.get('previewUrl') and norm(x.get('trackName')) == norm(track):
                return x['previewUrl'], cn
        time.sleep(0.8)
    return None, None


def main():
    apply = '--apply' in sys.argv
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    entries = json.loads(src[s:e].rstrip().rstrip(';'))

    print('artist/title swapped back:')
    for x in entries:
        fix = SWAPPED.get((x.get('year'), x.get('artist'), x.get('title')))
        if fix:
            print(f"  {x['year']}  artist {x['artist']!r} -> {fix[0]!r}"
                  f"\n        title  {x['title']!r} -> {fix[1]!r}")
            x['artist'], x['title'] = fix

    print('\napple previews:')
    found = {}
    for (year, artist, album), (term, track) in WANTED.items():
        url, coll = preview(term, album, track)
        print(f"  {'ok  ' if url else 'MISS'} {year} {artist} - {album} :: {track}"
              f"{'  <- ' + coll if coll else ''}")
        if url:
            found[(year, artist, album)] = url
        time.sleep(1.0)

    n = 0
    for x in entries:
        url = found.get((x.get('year'), x.get('artist'), x.get('title')))
        if url:
            x['audio'] = url
            n += 1
    print(f'\n{n} entries would get an Apple preview')

    if not apply:
        print('dry run - rerun with --apply')
        return
    open(DATA, 'w').write(
        src[:s] + json.dumps(entries, indent=2, ensure_ascii=False) + src[e:])
    print('wrote data.js')


if __name__ == '__main__':
    main()
