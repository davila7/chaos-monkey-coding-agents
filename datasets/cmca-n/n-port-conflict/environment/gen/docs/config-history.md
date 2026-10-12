# Configuration revisions

Everything under /app/config is versioned as a whole. Each change produces a new revision number. The files under /app/config are always the newest revision. Service files under /app/services are not versioned and do not change between revisions.

/app/config-history keeps the older contents:

- `INDEX` lists every revision with its date and a one line summary.
- `r<NNNN>/CHANGES` describes revision NNNN and lists the files it changed.
- `r<NNNN>/prev/<path>` is the content `<path>` had just before revision NNNN changed it, that is, as of revision NNNN - 1. `<path>` is relative to /app/config.

To get a file as it was at revision R:

1. Go through the history directories for revisions greater than R, from the lowest number up.
2. The first one that has `prev/<path>` holds the file as of revision R.
3. If none of them has it, the file has not changed since revision R and the copy under /app/config is the one to use.

Every file under /app/config existed at every revision listed in INDEX.
