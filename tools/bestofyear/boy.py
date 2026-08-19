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
    reasoning, and the same steps, as entryKey() in best-of-year.js.

    Both of the steps below are load-bearing, and a U+3000-U+9FFF range plus a
    drop-every-combining-mark filter - which is what this was - gets each of them wrong. The
    recompose saves a voiced kana: NFKD splits ダ into タ plus U+3099, and dropping every mark
    folds it onto タ, so ダ and タ dedup as one album. The category test saves everything the
    range left out, which is every script above U+9FFF and every Latin letter with no
    decomposition - 한 and Lindstrøm's ø, and the ones that fold to '' are the CJK case again.
    """
    s = unicodedata.normalize('NFKD', s or '')
    s = re.sub('[\\u0300-\\u036f]', '', s)
    s = unicodedata.normalize('NFC', s).lower()
    return ''.join(c for c in s if unicodedata.category(c)[0] in 'LN')
