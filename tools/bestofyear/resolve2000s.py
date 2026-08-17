#!/usr/bin/env python3
"""Resolve album art + 30s audio preview for the 2000s Best-of-Year import.

Art:   iTunes Search API, falling back to MusicBrainz + Cover Art Archive.
Audio: Deezer supplies per-track popularity rank; iTunes supplies a durable preview
       URL. Deezer's own preview URLs are NOT used - they carry a ~24h expiry token.

Results are cached to CACHE so the run is resumable and re-runnable for free.

Usage: python3 resolve2000s.py [--only YEAR]
"""
import json, os, re, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, '/tmp')
from sheet import records, fixed

DATA = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/data.js'
CACHE = '/tmp/cache2000s.json'
UA = {'User-Agent': 'indie-rock-timeline/1.0 (xavjiang@gmail.com)'}


def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', s.lower())


def get(url, tries=3, raw=False):
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=30)
            return r.read() if raw else json.load(r)
        except Exception:
            if n == tries - 1:
                raise
            time.sleep(1.5 * (n + 1))


# ---------------------------------------------------------------- album matching

REJECT = ('karaoke', 'tribute', 'in the style of', 'made popular by', 'originally performed',
          'instrumental', 'cover', 'lofi', 'music of')
DEMOTE = (('remix', 6), ('super deluxe', 4), ('deluxe', 3), ('anniversary', 3),
          ('expanded', 2), ('live', 4), ('demo', 3), ('remaster', 1))
TRACK_DEMOTE = ('remix', 'version', 'live', 'edit', 'instrumental', 'a cappella',
                'acapella', 'reprise', 'interlude', 'demo', 'skit')


def base_title(t):
    return norm(re.sub(r'[\(\[].*?[\)\]]', '', t or ''))


def score_album(alb, artist, album, year):
    title = alb.get('title') or ''
    low = title.lower()
    an = norm((alb.get('artist') or {}).get('name'))
    if not (norm(artist) in an or an in norm(artist)):
        return -99
    if any(w in low for w in REJECT):
        return -99
    s = 0.0
    if base_title(title) == norm(album):
        s += 6
    elif norm(album) in norm(title) or norm(title) in norm(album):
        s += 3
    else:
        return -99
    for word, pen in DEMOTE:
        if word in low:
            s -= pen
    n = alb.get('nb_tracks') or 0
    if n > 30:
        s -= 3
    elif n and n < 7:
        s -= 4
    ry = int((alb.get('release_date') or '0')[:4] or 0)
    if ry:
        s -= min(abs(ry - year), 20) / 10.0
    s += min(n, 20) / 100.0
    return s


def deezer_album(artist, album, year):
    cands = []
    for q in (f'artist:"{artist}" album:"{album}"', f'{artist} {album}'):
        try:
            r = get('https://api.deezer.com/search/album?' +
                    urllib.parse.urlencode({'q': q, 'limit': 15}))
            cands += r.get('data', [])
        except Exception:
            pass
        time.sleep(0.3)
    # Deezer's album search index misses some records entirely - walk the artist catalogue.
    try:
        ar = get('https://api.deezer.com/search/artist?' +
                 urllib.parse.urlencode({'q': artist, 'limit': 3}))
        for a in ar.get('data', []):
            if norm(a['name']) == norm(artist):
                cands += get(f"https://api.deezer.com/artist/{a['id']}/albums?limit=300").get('data', [])
                break
        time.sleep(0.3)
    except Exception:
        pass

    seen, uniq = set(), []
    for alb in cands:
        if alb.get('id') not in seen:
            seen.add(alb['id'])
            uniq.append(alb)

    # Search results carry no release_date; fetch it for the plausible few so
    # score_album can reject later reissues.
    shortlist = sorted(uniq, key=lambda a: -score_album(a, artist, album, year))[:6]
    for alb in shortlist:
        if not alb.get('release_date'):
            try:
                alb.update(get(f"https://api.deezer.com/album/{alb['id']}"))
            except Exception:
                pass
            time.sleep(0.2)

    best, best_s = None, 0
    for alb in shortlist:
        s = score_album(alb, artist, album, year)
        if s > best_s:
            best, best_s = alb, s
    if best:
        return best
    # Some records only exist on Deezer as a deluxe/anniversary reissue (e.g. the
    # Avalanches). Penalties push those below zero - take the best one anyway, as
    # long as it cleared the artist/title gate in score_album.
    scored = [(score_album(a, artist, album, year), a) for a in shortlist]
    scored = [(s, a) for s, a in scored if s > -50]
    return max(scored, key=lambda x: x[0])[1] if scored else None


def pick_track(tracks):
    """Most popular track, preferring a clean recording over a remix/alt version."""
    clean = [t for t in tracks if not any(w in (t.get('title') or '').lower() for w in TRACK_DEMOTE)]
    return max(clean or tracks, key=lambda t: t.get('rank', 0))


# ---------------------------------------------------------------------- iTunes

def itunes_album(artist, album):
    """Return (artworkUrl600, collectionId, collectionName) for the album."""
    for term in (f'{artist} {album}', album):
        try:
            r = get('https://itunes.apple.com/search?' +
                    urllib.parse.urlencode({'term': term, 'entity': 'album', 'limit': 25}))
        except Exception:
            continue
        best, best_s = None, 0
        for x in r.get('results', []):
            cn, an = x.get('collectionName') or '', x.get('artistName') or ''
            if not (norm(artist) in norm(an) or norm(an) in norm(artist)):
                continue
            if any(w in cn.lower() for w in REJECT):
                continue
            s = 6 if base_title(cn) == norm(album) else (3 if norm(album) in norm(cn) else 0)
            if not s:
                continue
            for word, pen in DEMOTE:
                if word in cn.lower():
                    s -= pen
            if s > best_s:
                best, best_s = x, s
        if best:
            art = (best.get('artworkUrl100') or '').replace('100x100bb', '600x600bb')
            return art or None, best.get('collectionId'), best.get('collectionName')
        time.sleep(0.25)
    return None, None, None


def itunes_preview(artist, track, album, collection_id=None):
    """Durable Apple preview URL for a track, preferring the right album."""
    if collection_id:
        try:
            r = get('https://itunes.apple.com/lookup?' +
                    urllib.parse.urlencode({'id': collection_id, 'entity': 'song', 'limit': 60}))
            for x in r.get('results', [])[1:]:
                if norm(x.get('trackName')) == norm(track) and x.get('previewUrl'):
                    return x['previewUrl'], x.get('collectionName')
        except Exception:
            pass
        time.sleep(0.2)
    for term in (f'{artist} {track} {album}', f'{artist} {track}'):
        try:
            r = get('https://itunes.apple.com/search?' +
                    urllib.parse.urlencode({'term': term, 'entity': 'song', 'limit': 25}))
        except Exception:
            continue
        c = [x for x in r.get('results', []) if x.get('previewUrl')
             and norm(x.get('trackName')) == norm(track)]
        exact = [x for x in c if norm(album) in norm(x.get('collectionName'))
                 or norm(x.get('collectionName')) in norm(album)]
        pick = (exact or c or [None])[0]
        if pick:
            return pick['previewUrl'], pick.get('collectionName')
        time.sleep(0.25)
    return None, None


# ----------------------------------------------------------------- MusicBrainz

def musicbrainz_art(artist, album):
    """Cover Art Archive front image, for records Apple's catalogue lacks."""
    try:
        q = urllib.parse.urlencode({
            'query': f'releasegroup:"{album}" AND artist:"{artist}"', 'fmt': 'json', 'limit': 5})
        r = get(f'https://musicbrainz.org/ws/2/release-group?{q}')
        time.sleep(1.1)  # MusicBrainz asks for <=1 req/sec
    except Exception:
        return None
    for rg in r.get('release-groups', []):
        if not (norm(album) in norm(rg.get('title')) or norm(rg.get('title')) in norm(album)):
            continue
        for url in (f"https://coverartarchive.org/release-group/{rg['id']}/front-500",):
            try:
                urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers=UA), timeout=20)
                return url
            except Exception:
                pass
        # Release-group art 500s for some records; walk individual releases instead.
        try:
            rel = get(f"https://musicbrainz.org/ws/2/release?release-group={rg['id']}&fmt=json&limit=10")
            time.sleep(1.1)
            for x in rel.get('releases', []):
                url = f"https://coverartarchive.org/release/{x['id']}/front-500"
                try:
                    urllib.request.urlopen(urllib.request.Request(url, method='HEAD', headers=UA), timeout=20)
                    return url
                except Exception:
                    pass
        except Exception:
            pass
    return None


# --------------------------------------------------------------------- driver

def targets():
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    entries = json.loads(src[s:e].rstrip().rstrip(';'))
    have = {(norm(x.get('title')), norm(x.get('artist')))
            for x in entries if x.get('type') == 'album'}
    recs, _ = records()
    out = []
    for r in recs:
        if not r.get('Year'):
            continue
        y = int(float(r['Year']))
        if not (2000 <= y <= 2009) or y == 2002:
            continue
        if (norm(r['Albums']), norm(r['Act'])) in have:
            continue
        out.append((y, r['Albums'], r['Act']))  # raw sheet strings = cache key
    return out


def main():
    only = None
    if '--only' in sys.argv:
        only = int(sys.argv[sys.argv.index('--only') + 1])
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = targets()
    if only:
        todo = [t for t in todo if t[0] == only]

    for n, (year, album, artist) in enumerate(todo, 1):
        key = f'{year}|{artist}|{album}'
        if key in cache:
            continue
        album, artist = fixed({'Albums': album, 'Act': artist})
        rec = {'year': year, 'album': album, 'artist': artist,
               'art': None, 'audio': None, 'track': None, 'notes': []}
        try:
            art, cid, cname = itunes_album(artist, album)
            rec['art'] = art
            if not art:
                rec['art'] = musicbrainz_art(artist, album)
                rec['notes'].append('art:musicbrainz' if rec['art'] else 'art:NONE')

            alb = deezer_album(artist, album, year)
            if alb:
                tracks = [t for t in get(f"https://api.deezer.com/album/{alb['id']}/tracks?limit=200")
                          .get('data', []) if t.get('rank') is not None]
                if tracks:
                    top = pick_track(tracks)
                    rec['track'] = top['title']
                    url, coll = itunes_preview(artist, top['title'], album, cid)
                    rec['audio'] = url
                    if not url:
                        rec['notes'].append('audio:NONE')
                else:
                    rec['notes'].append('audio:no-tracks')
            else:
                rec['notes'].append('audio:no-deezer-album')
        except Exception as ex:
            rec['notes'].append(f'ERROR {type(ex).__name__}: {ex}')

        cache[key] = rec
        json.dump(cache, open(CACHE, 'w'), indent=1, ensure_ascii=False)
        flag = '' if (rec['art'] and rec['audio']) else '  <-- ' + ','.join(rec['notes'])
        print(f'[{n}/{len(todo)}] {year} {artist} - {album}{flag}', flush=True)

    done = [c for c in cache.values() if c['art'] and c['audio']]
    print(f'\ncomplete: {len(done)}/{len(cache)} have both art and audio')


if __name__ == '__main__':
    main()
