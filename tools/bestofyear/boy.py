"""Read/write the BEST_OF_ENTRIES array in bestof-data.js.

Kept separate from build2000s.py because that script predates the view fork and
still targets data.js/ENTRIES. It also predates YEAR_NOTES, so its `\\nconst \\w+`
terminator lands on the *comment* above the notes and takes the closing `];` with
it - the array here is delimited explicitly instead.
"""
import json, re, unicodedata

DATA = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/bestof-data.js'


def _bounds(src):
    i = src.index('const BEST_OF_ENTRIES')
    s = src.index('[', i)
    e = src.index('\n];', s) + len('\n];')
    return s, e


def load():
    """-> (src, start, end, entries). src[start:end] is the array literal."""
    src = open(DATA).read()
    s, e = _bounds(src)
    return src, s, e, json.loads(src[s:e].rstrip().rstrip(';'))


def save(src, s, e, entries):
    open(DATA, 'w').write(
        src[:s] + json.dumps(entries, indent=2, ensure_ascii=False) + ';' + src[e:])


def norm(s):
    """Fold to a comparison key, keeping letters and digits of any script.

    A /[^a-z0-9]/ strip collapses every CJK title to '', so 椎名林檎's album and 青葉市子's
    would compare equal - to each other and to any other CJK record. The build scripts use
    this for dedup, so that reads as 'already imported' and silently drops the album. Same
    reasoning, and the same character range, as entryKey() in best-of-year.js.
    """
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^0-9a-z　-鿿]', '', s.lower())
