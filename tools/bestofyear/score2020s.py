"""How well an Apple collection name answers to the album we asked for.

Split out of the resolver because three scripts need it: resolve2020s.py to choose a
collection, audit2020s.py to vouch for what it chose, and build2020s.py to decide whether
Apple's spelling of a title is worth taking over the sheet's.

The rules are gapfill2010s's, which were written against the ~35 albums the first 2010s
import got wrong, plus the traps that only appear once you search for 2020s releases.
There is no separate gapfill pass this decade - resolve2020s does one catalogue-first
pass - so this is the only scorer in play.
"""
import re
import gapfill as G
import resolve2000s as R
from gapfill2010s import suffix_ok, censored_match

# 'sped up' and 'nightcore' are the 2020s equivalents of the 2010s' 'slowed'/'reverb'
# edits: whole shadow catalogues of retitled uploads that match on the base name.
REJECT = R.REJECT + ('renditions', 'performs', 'playlist', 'slowed', 'reverb', 'rework',
                     '8-bit', 'string quartet', 'workout mix', 'study music',
                     'sleep music', 'music for sleep', 'sped up', 'nightcore',
                     'tiny desk')

# Same shape as the 2010s table. 'deluxe' stays at R's 3 rather than being raised:
# SZA's LANA only exists as "SOS Deluxe: LANA", so a heavier penalty would zero out the
# one collection that carries it.
DEMOTE = tuple((w, 1 if w == 'expanded' else p) for w, p in R.DEMOTE) + (
    ('single', 6), ('radio edit', 3), ('pt.', 2), ('vol.', 2),
    ("'s version", 6), ('re-recorded', 6))


# REJECT and DEMOTE terms have to match whole words, not bare substrings. Naive `w in low`
# rejects MJ Lenderman's "Manning Fireworks" for 'rework' and Daft Punk's "Discovery" for
# 'cover', and docks "Everything is alive" and "Weather Alive" 4 points for 'live'. It is the
# same trap the EP rule at the bottom of score_coll already sidesteps by hand.
#
# A plain \b on both ends overcorrects the other way: the terms are stored as stems, and
# Apple writes the inflected form - 'remaster' has to reach "Remastered", 'demo' has to reach
# "Demos", 'remix' has to reach "Remixes". So the left edge is a hard word boundary and the
# right edge allows only a short list of endings. "Demos" matches, "Demonios" does not.
#
# The boundary is applied per edge and only where the term itself starts or ends in a word
# character: "'s version" opens on an apostrophe and must still match "Taylor's Version",
# and 'pt.' closes on a period and must not pick up "Capt.".
_SUFFIX = r'(?:s|d|ed|es|ing)?'


def _term_re(w):
    left = r'(?<![a-z0-9])' if w[0].isalnum() else ''
    right = _SUFFIX + r'(?![a-z])' if w[-1].isalnum() else ''
    return re.compile(left + re.escape(w) + right)


_REJECT_RE = [_term_re(w) for w in REJECT]
_DEMOTE_RE = [(_term_re(w), pen) for w, pen in DEMOTE]


def score_coll(name, album):
    """0 means no. See gapfill2010s.score_coll - this is that function, retuned.

    Only suffix padding counts, and only when it opens with a delimiter, so
    "THE TORTURED POETS DEPARTMENT: THE ANTHOLOGY" answers to TTPD at a lower score than
    the plain edition, while "BRAT and it's completely different but also still brat"
    does not answer to brat at all.
    """
    # Fold the curly apostrophe: Apple writes "Taylor’s Version" with U+2019, so the
    # "'s version" demote - stored with a straight quote - never fired on the one family of
    # releases it exists for. Every re-recording was scoring as if it were the original.
    low = (name or '').lower().replace('’', "'")
    if not low or any(rx.search(low) for rx in _REJECT_RE):
        return 0
    # G.amp on both sides. G.norm strips punctuation but leaves letters, so '&' vanishes
    # while 'and' survives: "Slanted & Enchanted" norms to slantedenchanted and "Slanted and
    # Enchanted" to slantedandenchanted, which score 0 against each other. Pavement,
    # Revolting Cocks and Sebadoh all failed to resolve on exactly that, and Crosby, Stills
    # & Nash only got in because a hand-written TITLE_FIX papered over it.
    nm, alb = G.amp(name), G.amp(album)
    base, want, whole = R.base_title(nm), G.norm(alb), G.norm(nm)
    if 'feat.' in low and base != want:
        return 0
    if base == want or whole == want or censored_match(nm, want):
        s = 6.0
    elif whole.startswith(want) and suffix_ok(nm, want):
        s = 3.0
    elif whole.startswith(want) and len(want) >= 12:
        s = 2.0
    else:
        return 0
    for rx, pen in _DEMOTE_RE:
        if rx.search(low):
            s -= pen
    # An EP is not the album. Can't go in DEMOTE as a bare 'ep' - that fires on "deep"
    # and "September" - and can't be an unconditional suffix rule either, or a sheet row
    # that genuinely names an EP would be penalised for matching itself. So it only
    # applies when Apple added the marker and the sheet didn't ask for one.
    if re.search(r'[-–—(\[]\s*ep\s*[)\]]?\s*$', low) and not want.endswith('ep'):
        s -= 6
    return s if s > 0 else 0
