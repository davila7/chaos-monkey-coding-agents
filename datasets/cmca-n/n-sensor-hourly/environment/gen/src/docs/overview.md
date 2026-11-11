# Hourly station product: overview

The weather and air stations of the network sample their sensors every few
seconds or minutes and keep the readings in a logger. When a logger gets a
connection it uploads what it holds as a text file, a logger dump. The hourly
product turns all dumps of all stations into one value per station, hour and
quantity, which the forecasting and air quality teams load as it is.

This note says what goes in, what comes out and in which order the work is
done. The rules for each step live in their own notes:

| Note | Covers |
|---|---|
| `files.md` | logger dumps: lines, directives, data rows, missing values |
| `clock.md` | logger time zones, clock drift and sync lines, repeated rows |
| `quantities.md` | the quantities, their units and conversions, valid ranges |
| `aggregation.md` | hours, coverage, means, wind direction, rain |
| `output.md` | the hourly file |
| `changelog.md` | what changed between versions of these rules |

Where this note and a numbered rule in another note seem to disagree, the
numbered rule wins. The rules apply to every station and every period the
same way: nothing in them depends on a particular station, logger, file or
date.

## 1. Inputs

1.1 An input directory holds logger dumps: every regular file in it whose
name ends in `.log`. Other files are not dumps and are ignored. The directory
has no subdirectories that matter.

1.2 A station uploads many dumps. Dumps overlap in time, and a logger can
upload a period again later with some values changed (a reissue). The file
name says nothing reliable about the station, the period or the order of the
uploads; the directives inside the file do (`files.md` 3).

## 2. Steps

1. Read every dump (`files.md`), converting each value to its canonical unit
   (`quantities.md` 2) and dropping values that are missing or out of range
   (`files.md` 6, `quantities.md` 3).
2. Put the logger time of every row on UTC (`clock.md` 1).
3. Keep one row per station and logger instant (`clock.md` 3).
4. Correct every row for clock drift (`clock.md` 2).
5. Assign each row to its hour (`aggregation.md` 1) and compute the hourly
   values (`aggregation.md` 2 to 5).

Then write every hour of every station to one file (`output.md`).

## 3. Terms

- A **logger time** is a date and time as the logger's clock showed it, in
  the logger's own time zone (`clock.md` 1).
- The **logger UTC instant** of a row is its logger time moved to UTC with the
  `tz` of its file. It still carries the logger's clock error.
- The **corrected time** of a row is its logger UTC instant plus the clock
  offset at that instant (`clock.md` 2). It is the best estimate of when the
  reading was taken.
- A **reading** of a quantity is one value in one data row that is not
  missing and is inside the valid range of the quantity.
- The **interval** of a station is the time between two readings of its
  logger, in seconds.

## 4. Running the program

4.1 The program reads one input directory and writes one hourly file:

    python3 /app/bin/hourly.py INPUT_DIR OUTPUT_FILE

It uses only the Python standard library, reads nothing outside `INPUT_DIR`
and writes nothing but `OUTPUT_FILE`. The same input gives the same output
wherever the input directory is.

4.2 The dumps are well formed: every data row has one field per column of
its `columns` line, every directive the rules require is present, and every
time is a real date and time. A program does not have to check this.
