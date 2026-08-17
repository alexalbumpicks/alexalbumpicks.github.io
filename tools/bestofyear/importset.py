"""Which years an import pass covers, and where its resolve cache lives.

resolve/audit/build2020s hardcoded both. The pre-2000 pass needs those same three scripts
over a different set of years, and copying them a fourth time would mean a fourth copy of
the scorer wiring, the storefront fallbacks and the multi-record handling to keep in step -
which is how the 2010s ended up with a resolver and a gapfill that disagreed.

So the year set moved out here and the scripts take `--set NAME`. They still default to
'2020s', which is what their filenames say and what every earlier invocation meant.

Year sets are not always contiguous: `pre2000` is the handful of pre-2000 years the sheet
has enough rows in to be worth importing, not a decade.
"""
import sys

SETS = {
    '2020s':   (set(range(2020, 2025)), '/tmp/cache2020s.json'),
    'pre2000': ({1969, 1993, 1994, 1997, 1998}, '/tmp/cachepre2000.json'),
    # Everything else before 2000. 'pre2000' was the five years with fifteen rows apiece,
    # picked when that looked like a meaningful cut - it isn't. A thin year just means the
    # records in it haven't had a proper listen yet, so the rest belong on the site too and
    # the split here is only about which pass resolved them.
    #
    # Stops at 1999: 2025-26 are their own set below.
    'pre2000rest': ({y for y in range(1954, 2000)}
                    - {1969, 1993, 1994, 1997, 1998}, '/tmp/cachepre2000rest.json'),
    # The current years, and the only ones left in the sheet. Held back from the pre-2000
    # pass because Alex said 2025 wasn't logged properly - which is a statement about how
    # complete the list is, not about whether the rows in it are real. They are, so they
    # import like any other year; the year will just keep growing after this.
    #
    # It did grow, and that is why this set is now in APPEND_ONLY. The first pass found these
    # years empty and numbered them from scratch, which was right then; since then Alex has
    # ranked both by hand, so every later pass is topping up a year that already has an order.
    # That is the same situation as 'addendum' and gets the same rule. Unlike 'addendum' the
    # year list here does not grow - 2025 and 2026 are the years, more rows just keep landing
    # in them.
    'current': ({2025, 2026}, '/tmp/cachecurrent.json'),
    # Rows Alex added to the sheet after every year in it had already been imported once.
    # Unlike every set above, this is not a block of new years: it is a scattering of albums
    # dropped into years that are already on the site and already hand-ranked - which is why
    # it is in APPEND_ONLY below.
    #
    # This one is open-ended. It grew four times during the import that created it, while the
    # sheet was being edited in another window, so treat the year list as a running total and
    # just add to it - re-running resolve/audit/build only picks up rows that aren't on the
    # site yet, and the append-only rule means a re-run cannot disturb what is.
    'addendum': ({1982, 1986, 1988, 1989, 1990, 1993, 1994, 1995, 1996, 1997,
                  2005, 2007, 2008, 2009, 2010, 2012, 2013, 2019},
                 '/tmp/cacheaddendum.json'),
}

# Sets whose years already have a running order that the import must not disturb.
#
# The normal build renumbers a year from scratch - sheet rows first in sheet order, then
# whatever else the year holds. That is right for a year arriving from nothing and wrong for
# one Alex has since re-ordered by hand, where it would quietly rewrite the lot. For these sets
# the build leaves every existing entry's yearRank alone and numbers the new albums upwards from
# the year's current maximum, so nothing already placed moves.
#
# It also means these years must NOT be added to RERANKED_YEARS in best-of-year.js. There is no
# new baked order for a save to heal towards, and pointing one at them would take back exactly
# the hand-ranking this is protecting.
APPEND_ONLY = {'addendum', 'current'}


def _name(argv):
    argv = sys.argv if argv is None else argv
    name = argv[argv.index('--set') + 1] if '--set' in argv else '2020s'
    if name not in SETS:
        raise SystemExit(f'unknown --set {name!r}; known: {", ".join(sorted(SETS))}')
    return name


def pick(argv=None):
    """(years, cache_path) for the --set named on the command line."""
    return SETS[_name(argv)]


def append_only(argv=None):
    """True if this set must preserve the existing running order of its years.

    Separate from pick() rather than a third slot in the tuple because only the build cares -
    resolve and audit unpack the pair too, and widening it would churn both for nothing.
    """
    return _name(argv) in APPEND_ONLY
