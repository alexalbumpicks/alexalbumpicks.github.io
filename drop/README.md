Drop an exported `bestof-data.js` here and run `python3 tools/pull.py`.

This folder exists because macOS gates `~/Downloads` and `~/Desktop` behind a per-app
permission that the shell does not always hold, so an export sitting there can be
invisible to the tooling. Anything inside the repo is readable, so this always works.

Nothing here is deployed. `drop/*.js` is gitignored; this README is not.
