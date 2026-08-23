# Working on this repo

Alex's album site. Vanilla JS/HTML/CSS, no build step, no npm, deployed on GitHub Pages.

## The one rule that overrides everything

**Alex's own words are never edited.** Not his Chinese, not his English, not his punctuation,
capitalisation, spacing or typos. If a blurb has a curly apostrophe next to a straight one in the
same sentence, both survive. If a sentence reads like it has a slip in it, mention it and leave it.
Every write script that touches a blurb verifies the stored text byte-for-byte against what he
pasted, and prints `VERBATIM OK` or refuses.

House style applies only to **English that Claude writes** - the translations. Four blurbs carry
Alex's own English (Showgirl, Ultraviolence, Gyrate, Saint Cloud) and are exempt; `t_blurbs.js`
scopes the checks around them by name rather than dropping them.

### The one exception: labels, not prose

Alex has asked that mistakes be corrected rather than queried, and that song titles be preferred
where a paste is ambiguous. That licence covers the **label** half of a paste - the album name,
artist and song he types to identify what a blurb or lyric belongs to. Those are metadata, and being
wrong there breaks a lookup:

- `Confessions 2` -> `CONFESSIONS II`, the name retired at schema 32; the literal finds nothing
- `cursive` -> `Cursive`, `Governor's Waltz` -> `The Governor’s Waltz`, matching the entry's own
  `audioTrack`, because one album spelling one track two ways is worse than either spelling alone
- `four women` -> `Four Women`, because that is the track's styling - while `anthems` and `the cure`
  stay lowercase, for exactly the same reason

**It does not extend one word into his writing.** A blurb is stored byte-for-byte as sent, typos and
mixed apostrophes and all, and every write script still verifies it or refuses. Casing follows the
record; prose follows Alex.

## Who edits what

Splitting this way is what stops the two write paths colliding.

| Alex, in the editor | Claude, by script |
|---|---|
| add / delete albums | blurbs and translations |
| ranks, art, audio, tags | cross-links (`reviewLinks`) |
| labels, Apple Music links | lyric pull quotes, `sensitive` flags |

Alex pastes a review into chat; Claude writes it to `bestof-data.js`, verifies it verbatim, adds any
links, updates the harnesses and stamps. Nothing about a blurb goes through the editor.

## The collision, and how to avoid it

The editor holds a snapshot of `bestof-data.js` from **whenever the page loaded**, in localStorage.
Anything written to the file after that is not in the snapshot, and saving would erase it.

- **Reload the editor after Claude writes anything.** That is the whole fix.
- Both write paths refuse rather than clobber: `⤓ save to repo` re-reads the file and compares, and
  `tools/pull.py` does the same from outside. Both name what would be lost and stop.
- If a refusal appears, do not force it. Reload the editor, export again, retry.

## Getting editor work into the file

The editor saves to localStorage. On Chrome it also writes through to `bestof-data.js` on every
edit; everywhere else that step is manual. Until the file is written, a review exists nowhere but
the browser - not in git, not on the site, not visible to Claude.

**Setup, once per machine**

1. Start the server. `file://` is not a secure context and the write-through does not exist there:
   ```
   albums --open
   ```
   `albums` is a symlink in `~/.local/bin` (already on PATH) pointing at `./serve` in this repo, so
   it runs from any directory. Inside the repo `./serve` is the same thing. NOT part of the repo -
   a fresh clone has `serve` but no `albums`; recreate with
   `ln -sf "$PWD/serve" ~/.local/bin/albums`.

   Safe to run twice - if it is already up it says so and points at it rather than clashing on the
   port. `--open` also launches the editor in Chrome; plain `albums` just prints the URLs.

   **A blank editor page is usually a cached one.** `editor.html` carries no `?v=` - the CSS and JS
   all do, but the page itself does not - and the server sends only `Last-Modified`. A blank or
   truncated response cached while the server was down or wedged will be served back forever
   without a re-request. `Cmd+Shift+R` fixes it. If that becomes a habit rather than a one-off,
   make `stamp.py` version `editor.html` too.

   The server is `ThreadingHTTPServer`, deliberately. The single-threaded `socketserver.TCPServer`
   this used to be wedges permanently on one keep-alive connection a browser leaves open: the
   process stays alive, keeps the listening socket, and answers nothing, so `ps` and `lsof` both
   report a healthy server while the browser shows a blank page. If a page ever goes blank,
   `curl -s -o /dev/null -m 3 -w '%{http_code}\n' http://localhost:8123/editor.html` tells you in
   one line - `200` serving, `000` dead.
2. Open `http://localhost:8123/editor.html` in **Chrome**. Always this origin - never
   `127.0.0.1:8123`, never `file://`. Each is a separate localStorage bucket, and mixing them
   splits the work across three invisible copies.
3. Click **⤓ save to repo** once. Pick the repo's existing `bestof-data.js` and confirm the
   overwrite. That grants a file handle, which is stored in IndexedDB and reused from then on.

**Every session after that**

1. `albums --open` (from anywhere).
2. Edit. Each change writes through ~0.8s later; the button reads **⤓ saved to repo**.
3. **Watch the button.** Red means the file is behind and only a click can fix it:
   - `permission lapsed` - Chrome dropped the grant, usually after a restart. Click once.
   - `N would be lost` - Claude wrote to the file after this tab loaded. **Reload, then edit.**
   - `cannot read the file` - the file is missing or unparseable. Stop and look.
4. **Tell Claude**, who runs the harnesses and stamps. Auto-save writes the data file but does not
   touch the `?v=` cache busters in `index.html`, so an unstamped change can be invisible in a
   browser holding the old file.

**On Safari, or without a granted handle:** none of the above applies. Click Export, drop the file
in `drop/`, then `python3 tools/pull.py`. Safari has no File System Access API and never will here.

**Moving from Safari to Chrome:** export from Safari *first*. localStorage is per-browser and
per-origin, so a Safari `file://` bucket is invisible from Chrome on `localhost:8123` - two
independent walls. The Chrome editor will look empty of anything unexported, which reads exactly
like data loss and is not.

## Before saying a change is done

```bash
for f in t_blurbs t_links t_reader_provisional t_reader_nav t_crosslinks t_outkast t_sensitive t_lyric t_editor; do
o=$(osascript -l JavaScript tmp/$f.js 2>&1)
ok=$(printf '%s' "$o"|grep -c '^ok'); bad=$(printf '%s' "$o"|grep -c '^BAD')
[ "$ok" -eq 0 ] && bad="HARNESS DID NOT RUN: $o"
echo "$f: ok=$ok BAD=$bad"; printf '%s' "$o"|grep '^BAD'
done; true
python3 tools/stamp.py --apply
```

**The `ok=0` guard is mandatory.** A harness that throws prints nothing, and without the guard that
reads as passing. It has caught a real break: an unescaped apostrophe in `Mama's Gun` closed a JS
string and killed the whole file silently.

`osascript -l JavaScript` is the only JS runtime here - there is no node. `python3` is 3.9.
Harnesses read files relative to the repo root and throw on a bad cwd.

## Conventions that have bitten before

- **Stamp after every write to disk.** `tools/stamp.py --apply` rewrites the `?v=` cache busters.
  Skipping it means the change is live in the file and invisible in the browser.
- **Bump `STORAGE_SCHEMA_VERSION`** when existing ranks move or `audio` is hand-corrected, and add
  the affected years to `RERANKED_YEARS` at that version. A pure append needs neither. One bump per
  write to disk.
- **New fields need no bump** - `backfillEmptyFields` fills them on the next editor load. That is
  how `review`, `reviewLinks`, `lyric` and `sensitive` all shipped.
- **Cross-link targets may not sit in a provisional year** (`year < 1967`). The link resolves at
  write time and then fails closed on the page, silently. Scripts check this; the editor draws such
  a link struck through so it is visible rather than invisible.
- **Genre + Sub-genre go into `tags` verbatim.** A raw Score sets `rating`/`yearRank`; the score
  itself is never stored.
- **Apple/iTunes links only.** No Spotify.
- **Every year's ranks must be a clean 1..n.** `t_outkast.js` asserts this as a property; 1966, 1982
  and 2002 had drifted for a long time because the reader prints an album's *index*, not its stored
  `yearRank`, so the disagreement was invisible on the page.

## Known gaps

- **`editor.html`, `best-of-year.js`, `timeline.*`, `data.js`, `style.css` are untracked**, as is
  `tmp/` with all nine harnesses. Roughly 496K of work that exists on one laptop and in no commit.
- The only remote is `old-origin`, a public repo with a spreadsheet in its history.
- macOS TCC blocks the shell from `~/Downloads` and `~/Desktop`, which is why `drop/` exists.
