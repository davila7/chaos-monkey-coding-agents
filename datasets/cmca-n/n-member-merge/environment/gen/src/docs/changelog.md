# Changelog

## 3.2 (in progress)

- `merge`: finds the records of one person and merges them (`merge.md`).
  Reads `settings.json` and `keep_apart.csv`, which the secretary filled in
  for this release.

## 3.1

- `find` searches phone numbers by their digits.
- `pay` takes `--day`.

## 3.0

- Register format 3: `marketing` and `updated` in every record.
- The front desk app writes `updated` in local time with its offset from
  UTC (from March 2023).

## 2.4

- `aliases.json` is written with padded ids. Files written by release 2.3
  and earlier still have keys below `M-0100` without leading zeros.

## 2.0

- Records from the old spreadsheet imported on 2019-04-01, tagged
  `import-2019`. The import kept the spreadsheet's `DD/MM/YYYY` days and its
  `;`-separated tags, and recorded only the day of the import as the update
  time.
- Members merged by hand by the secretary keep their numbers in
  `aliases.json`.
