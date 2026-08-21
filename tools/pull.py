#!/usr/bin/env python3
"""Install an exported bestof-data.js from the browser's download folder into the repo.

WHY THIS EXISTS
---------------
The editor keeps every hand edit in localStorage (`indie_bestofyear_v1`) and only reaches
bestof-data.js when Export is clicked, which downloads a file that then has to be moved into the
repo by hand. Until that move happens a blurb written in the editor is invisible to anything
outside the browser - to the published site, to git, and to Claude. This script is the move, with
the checks that make it safe to do without reading the diff first.

The checks are the point, not the copy. The export is a full rewrite of the file from whatever
localStorage happens to hold, so it can silently drop anything written to bestof-data.js by a
script since the editor last loaded. backfillEmptyFields() covers most of that on the next editor
load - but only for fields that are EMPTY in the saved copy, and only if the editor has been
reloaded since. Export from a stale tab and the newer work is gone. So: refuse by default, print
exactly what would be lost, and make overriding an explicit choice.

    python3 tools/pull.py              # newest bestof-data.js in ~/Downloads
    python3 tools/pull.py <path>       # a specific file
    python3 tools/pull.py --dry-run    # report only, write nothing
    python3 tools/pull.py --force      # install even though fields would be lost

Nothing is stamped or tested here. On success it prints the two commands to run next.
"""
import json
import os
import re
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, 'bestof-data.js')
# Searched in order. The repo-local drop/ is first and is the one that always works: macOS TCC
# gates ~/Downloads and ~/Desktop behind a per-app grant that the shell running this script does
# not necessarily hold, and an export sitting in a folder we cannot list is the same as no export.
# Anything inside the repo is already readable, since that is where the work happens.
DROP = os.path.join(REPO, 'drop')
CANDIDATE_DIRS = [DROP, REPO,
                  os.path.expanduser('~/Downloads'),
                  os.path.expanduser('~/Desktop')]

# Losing one of these means losing writing or a hand-resolved link, not a re-derivable value.
PRECIOUS = ['review', 'reviewEn', 'reviewLinks', 'lyric', 'sensitive',
            'art', 'audio', 'appleMusic', 'label', 'tags']


def parse(path):
    src = open(path, encoding='utf-8').read()
    if 'const BEST_OF_ENTRIES' not in src:
        raise SystemExit('%s does not look like bestof-data.js (no BEST_OF_ENTRIES)' % path)
    i = src.index('const BEST_OF_ENTRIES')
    s = src.index('[', i)
    e = src.index('\n];', s) + len('\n];')
    entries = json.loads(src[s:e].rstrip().rstrip(';'))
    notes = {}
    m = re.search(r'const YEAR_NOTES = (\{.*?\n\});', src, re.S)
    if m:
        notes = json.loads(m.group(1))
    return entries, notes


def key(x):
    # Same identity the editor's entryKey() uses, minus the unicode folding - close enough to
    # pair entries across two copies of the same file, which is all this needs to do.
    return (x.get('type'), x.get('year'), (x.get('title') or '').lower().strip(),
            (x.get('artist') or '').lower().strip())


def newest_download():
    found, denied = [], []
    for d in CANDIDATE_DIRS:
        try:
            names = os.listdir(d)
        except PermissionError:
            denied.append(d)
            continue
        except OSError:
            continue
        for n in names:
            # Chrome numbers repeat downloads: bestof-data (1).js, bestof-data (2).js
            if re.match(r'^bestof-data( \(\d+\))?\.js$', n):
                p = os.path.join(d, n)
                if os.path.abspath(p) == DATA:
                    continue          # the repo's own file is not an incoming export
                found.append((os.path.getmtime(p), p))
    if found:
        found.sort()
        return found[-1][1]

    msg = ['No exported bestof-data.js found. Looked in:']
    for d in CANDIDATE_DIRS:
        tag = '  (permission denied - macOS has not granted this shell access)' if d in denied else ''
        msg.append('  %s%s' % (d.replace(os.path.expanduser('~'), '~'), tag))
    msg.append('')
    if denied:
        msg.append('Two ways round the denied folders, either is fine:')
        msg.append('  - drag the exported file into %s/ and re-run' % os.path.relpath(DROP, REPO))
        msg.append('  - or grant access in System Settings > Privacy & Security > Files and Folders')
    else:
        msg.append('Open the editor, click Export, then run this again - or pass the path directly.')
    raise SystemExit('\n'.join(msg))


def main():
    args = [a for a in sys.argv[1:]]
    dry = '--dry-run' in args
    force = '--force' in args
    paths = [a for a in args if not a.startswith('--')]
    incoming = paths[0] if paths else newest_download()

    age = (time.time() - os.path.getmtime(incoming)) / 60.0
    print('incoming : %s' % incoming)
    print('           exported %s' % (
        'just now' if age < 2 else '%.0f minutes ago' % age if age < 180 else '%.1f HOURS ago - is this the export you meant?' % (age / 60)))

    new, new_notes = parse(incoming)
    old, old_notes = parse(DATA)
    print('current  : %d entries -> incoming %d entries' % (len(old), len(new)))

    old_by, new_by = {key(x): x for x in old}, {key(x): x for x in new}
    added = [k for k in new_by if k not in old_by]
    removed = [k for k in old_by if k not in new_by]

    # --- what would be lost --------------------------------------------------------------------
    losses = []
    for k, o in old_by.items():
        n = new_by.get(k)
        if n is None:
            if any(o.get(f) for f in PRECIOUS):
                losses.append((k, 'ENTRY REMOVED', [f for f in PRECIOUS if o.get(f)]))
            continue
        gone = [f for f in PRECIOUS if o.get(f) and not n.get(f)]
        if gone:
            losses.append((k, 'fields dropped', gone))

    for k in sorted(added):
        print('  + %s %s / %s' % (k[1], new_by[k].get('title'), new_by[k].get('artist')))
    for k in sorted(removed):
        print('  - %s %s / %s' % (k[1], old_by[k].get('title'), old_by[k].get('artist')))

    nb_old = sum(1 for x in old if x.get('review'))
    nb_new = sum(1 for x in new if x.get('review'))
    if nb_new != nb_old:
        print('  blurbs %d -> %d' % (nb_old, nb_new))
    if old_notes != new_notes:
        print('  YEAR_NOTES differ (%d -> %d years)' % (len(old_notes), len(new_notes)))

    if losses:
        print()
        print('REFUSING - the incoming file would drop work already in bestof-data.js:')
        for k, what, fields in losses:
            print('  %s %s / %s: %s [%s]' % (k[1], k[2], k[3], what, ', '.join(fields)))
        print()
        print('This usually means the editor tab was opened before that work was written.')
        print('Reload the editor (backfill fills empty fields from the file), export again, retry.')
        print('If the loss is intentional, re-run with --force.')
        if not force:
            return 1
        print('--force given, installing anyway.')

    if not losses and not added and not removed and nb_old == nb_new:
        # Not proof of no change - a reworded blurb moves nothing counted above.
        same = open(incoming, encoding='utf-8').read() == open(DATA, encoding='utf-8').read()
        print('  no entries added or removed%s' % (', file is byte-identical' if same else ', but content differs'))

    if dry:
        print('\n--dry-run, nothing written.')
        return 0

    backup = DATA + '.bak'
    shutil.copy2(DATA, backup)
    shutil.copy2(incoming, DATA)
    print('\ninstalled. previous file kept at %s' % os.path.basename(backup))
    print('next:')
    print('  for f in t_blurbs t_links t_reader_provisional t_reader_nav t_crosslinks t_outkast t_sensitive t_lyric; do \\')
    print('    osascript -l JavaScript tmp/$f.js | grep -c "^ok"; done')
    print('  python3 tools/stamp.py --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
