# Sources

Each site folder holds the exports of six systems. They were set up by
different teams over the years, and each writes times its own way.

## site.json

`{"name": "...", "utc_offset": "+05:30"}`. The offset is the site's local
time, a fixed offset (none of our sites changes its clocks).

## tickets.csv (ticket system)

Columns `id`, `queue`, `opened`, `closed` (`closed` is empty while a ticket
is open). Times are ISO 8601 as the ticket system's export library writes
them: extended or basic form, with a fraction of a second or not, with `Z`,
an offset, or no offset at all. The ticket system runs on UTC, so a time
without an offset is UTC. A row whose time cannot be read is skipped with a
warning; the export has a few rows like that after every outage.

## escalations.csv (team leads' sheet)

Columns `ticket`, `at`, `to`. Team leads type `at` by hand in the site's
local time. The sheet keeps ISO dates as typed and turns hand-typed dates
into one of two layouts (`YYYY-MM-DD H:MM` with unpadded fields, or
`DD.MM.YYYY H:MM`).

## calls.log (phone switch)

One call per line, `EPOCH QUEUE SECONDS`, where `EPOCH` is Unix time in
seconds as the switch's clock writes it, often with a fraction. The switch
counts a call from the whole second it started in. Lines starting with `#`
are comments.

## chats.jsonl (chat service)

One JSON object per line: `id`, `queue`, `start_ms`, `end_ms`, Unix time
in milliseconds as JSON numbers. The chat service bills each chat from its
start to its end, both taken to the nearest second.

## roster.txt (HR)

One shift per line, `AGENT DD/MM/YY HH:MM-HH:MM`, in the site's local time.
HR writes the day first. `24:00` is the midnight at the end of the day, and
a shift that ends at or before its start ends the next day.

## closures.txt (facilities)

One closed day per line, `DATE REASON`, with the date either ISO
(`YYYY-MM-DD`) or the US form `MM/DD/YYYY`. A line whose date cannot be
read is ignored with a warning.
