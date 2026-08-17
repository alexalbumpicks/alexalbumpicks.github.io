#!/usr/bin/env python3
"""Fork data.js into a timeline store and a Best-of-Year store.

The two views currently share one ENTRIES array, which is why an album can't be deleted
from one without vanishing from the other. 176 albums appear in BOTH views, so this is a
fork rather than a partition: those 176 are copied into each side and the copies then
live independent lives.

Fields that mean nothing on the far side of the fork are dropped, so neither file carries
dead weight that would later confuse an edit:
  - era / movement / side are timeline layout concepts -> stripped from Best of Year
  - yearRank is a Best-of-Year ordering concept (timeline.js never reads it) -> stripped
    from the timeline
  - bestOfYearOnly / hideFromBestOfYear only existed to route entries between the two
    views -> dropped from both, the file an entry lives in now says where it shows

Usage: python3 split.py [--apply]
"""
import json, re, sys

ROOT = '/Users/alexziyujiang/Documents/GitHub/indie_rock_timeline/'
DATA = ROOT + 'data.js'
BOY  = ROOT + 'bestof-data.js'

BOY_DROP      = {'era', 'movement', 'side', 'bestOfYearOnly', 'hideFromBestOfYear'}
TIMELINE_DROP = {'yearRank', 'bestOfYearOnly', 'hideFromBestOfYear'}


def main():
    apply = '--apply' in sys.argv
    src = open(DATA).read()
    i = src.index('const ENTRIES'); s = src.index('[', i)
    m = re.search(r'\nconst \w+', src[s:]); e = s + m.start()
    entries = json.loads(src[s:e].rstrip().rstrip(';'))

    # Best of Year: every album the view shows today, in today's order.
    boy = [{k: v for k, v in x.items() if k not in BOY_DROP}
           for x in entries
           if x.get('type') == 'album' and not x.get('hideFromBestOfYear')]

    # Timeline: everything the timeline shows today - albums plus events and notes.
    tl = [{k: v for k, v in x.items() if k not in TIMELINE_DROP}
          for x in entries if not x.get('bestOfYearOnly')]

    shared = sum(1 for x in entries
                 if x.get('type') == 'album'
                 and not x.get('bestOfYearOnly') and not x.get('hideFromBestOfYear'))

    print(f'data.js today       {len(entries)} entries')
    print(f'  -> timeline       {len(tl)} entries '
          f'({sum(1 for x in tl if x.get("type") == "album")} albums '
          f'+ {sum(1 for x in tl if x.get("type") != "album")} events/notes)')
    print(f'  -> best of year    {len(boy)} albums')
    print(f'  copied into both  {shared}')
    ranked = sum(1 for x in boy if x.get('yearRank'))
    print(f'  yearRank preserved on {ranked} best-of-year albums')

    if not apply:
        print('\ndry run - rerun with --apply')
        return

    open(DATA, 'w').write(
        src[:s] + json.dumps(tl, indent=2, ensure_ascii=False) + src[e:])
    open(BOY, 'w').write(
        '// Albums for the Best of Year view (best-of-year.html).\n'
        '//\n'
        '// Deliberately separate from data.js: the two views were forked so that an album\n'
        '// can be deleted, reordered or re-rated in one without touching the other. Albums\n'
        '// that appear in both timelines exist as independent copies here - editing one side\n'
        '// does not change the other.\n'
        'const BEST_OF_ENTRIES = '
        + json.dumps(boy, indent=2, ensure_ascii=False) + ';\n')
    print(f'\nwrote {DATA}\nwrote {BOY}')


if __name__ == '__main__':
    main()
