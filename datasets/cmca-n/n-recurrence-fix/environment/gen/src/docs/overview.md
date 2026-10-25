# Agenda: overview

This note describes what the `agenda` package does, where its inputs live and
in which order the instances of an event are worked out. The rules for each
step live in their own notes:

| Note | Covers |
|---|---|
| `rules.md` | recurrence rules: the supported parts, how periods are expanded, COUNT and UNTIL |
| `zones.md` | the zone table, daylight saving changes, local times that are skipped or repeated |
| `events.md` | event files, extra and excluded dates, overrides, durations, the window |
| `output.md` | the event documents, the agenda listing, the text view, errors |
| `changelog.md` | what changed between releases of the package |

Notes under `docs/archive/` are kept for the record. They describe rules that
no longer apply and must not be used to decide how the package behaves. Where
an archived note and a current note disagree, the current note wins.

## 1. Purpose and scope

1.1 The package reads calendar events, each with an optional recurrence rule,
and lists the instances of each event that fall inside a reporting window. It
does not send invitations, keep attendees or resolve conflicts between events.

1.2 Every event belongs to one zone. Its start time, its extra and excluded
dates and its overrides are local wall times in that zone. The reporting window
and the sort order of every listing are in UTC.

1.3 An event is either expanded completely or not at all. When an event file
breaks a rule (an unknown zone, an unsupported rule part, an override that
changes nothing) the package raises an error for that event and writes nothing
for it. It never writes a partial document and never guesses a missing value.

1.4 The package uses only the Python standard library and does not read the
time zone database of the system it runs on. Zones are defined only by the
zone table of the data directory (`zones.md`).

## 2. Data directory

2.1 All inputs come from one data directory. Its layout is fixed:

    DATA/zones.json          the zone table
    DATA/agenda.json         the reporting window
    DATA/events/<uid>.json   one event per file, named after the event uid

2.2 `zones.json` and `agenda.json` are read once per run. Event files are read
when their event is expanded.

2.3 The data directory is input only. The package never writes to it.

2.4 All files are UTF-8 JSON objects. Unknown keys are ignored; missing
required keys are errors.

## 3. How the instances of an event are worked out

The steps below run in this order. Each step uses only results of earlier
steps.

3.1 **Resolve.** Read the event, look up its zone and parse its rule
(`rules.md` sections 2 and 3, `events.md` section 3).

3.2 **Generate.** Expand the rule from the event start into local start times,
in order, stopping at UNTIL (`rules.md` sections 4 and 5). The event start is
always the first of them.

3.3 **Count.** When the rule has COUNT, keep the first COUNT generated times.
COUNT is counted on the generated times, before any excluded date is taken
out: an excluded date still uses up one of the COUNT instances
(`rules.md` 5.2).

3.4 **Exclude and add.** Take out every time listed in `exdate`, then add every
time listed in `rdate` that is not excluded (`events.md` section 4). The
result is the set of recurrence ids of the event.

3.5 **Override.** Apply each override to the instance whose recurrence id it
names: move it, change its duration or cancel it (`events.md` section 5).

3.6 **Place.** Turn each instance's local start into UTC with the event's zone
and add the duration (`zones.md` section 4, `events.md` section 6).

3.7 **Window.** Keep the instances that overlap the reporting window and sort
them (`events.md` section 7, `output.md` section 2).

## 4. Command line

    python -m agenda expand UID [--data DIR]
    python -m agenda show UID [--data DIR]
    python -m agenda run --out OUT [--data DIR]

4.1 `--data` names the data directory. When it is left out, `./data` is used.

4.2 `expand` prints the event document as JSON. `show` prints the text view
(`output.md` section 4). Both exit with status 1 and print the error to
standard error when the event cannot be expanded.

4.3 `run` expands every event of the data directory and writes
`OUT/events/<uid>.json` for each one, `OUT/agenda.json` with the instances of
all events, and `OUT/errors.json` with the events that could not be expanded.
`run` exits with status 0 even when some events could not be expanded, and
with status 1 only when the zone table or the window cannot be read.

4.4 Documents are written as JSON with two-space indentation, keys in the
order `output.md` lists them, followed by a newline.

## 5. Checking the package

5.1 The unit tests under `tests/` cover the building blocks and a set of event
documents that were reviewed by hand. Run them from the package root with:

    python -m unittest discover -s tests -t .

5.2 `tools/check.py` expands every event of a data directory and checks
properties that every correct document has (durations, ordering, local times
that agree with their UTC times, instances inside the window). It reports, per
rule, how many events break one. It does not expand any rule itself, so a
clean run does not mean every rule holds. The notes in this directory remain
the reference.

5.3 Neither the tests nor the check decide the rules. When a test and a note
disagree, the note is right and the test is reported.
