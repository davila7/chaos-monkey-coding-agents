# Changelog of the hourly rules

## 4.0 (2027-03)

- Coverage is enough at 75 percent of the expected count (`aggregation.md`
  2.2). Up to 3.x the threshold was 60 percent, and the air quality team
  found hourly means built from a little more than half an hour of samples
  that did not match the station's own displays.
- Repeated rows are found by logger UTC instant (`clock.md` 3.3). Up to 3.x
  they were found by the logger time as written, which kept both copies of
  every sample uploaded before and after a logger changed its time zone.

## 3.2 (2026-11)

- Clock offsets between sync points are rounded down (`clock.md` 2.4). 3.1
  rounded them to the nearest second; 3.0 cut off the decimals, which rounds
  negative offsets up.
- Offsets are held at the first and last sync point (`clock.md` 2.4). 3.1
  extrapolated the line through the two nearest sync points, which moved the
  first and last hours of a station by minutes when its logger was slow to
  reach the time service.

## 3.1 (2026-07)

- A reissued row replaces the older row as a whole (`clock.md` 3.2). 3.0
  took each field from the newest file that had a value for it, which brought
  back values the station operator had withdrawn.
- Wind direction is a vector mean of unit vectors, calm samples left out
  (`aggregation.md` 4). Up to 3.0 it was the arithmetic mean of the angles,
  which gave 180 for winds between 350 and 10 degrees.

## 3.0 (2026-03)

- Hours are named by their end (`aggregation.md` 1.1), as the forecasting
  system names them. Up to 2.x an hour was named by its start.
- Rain is worked out from counter increments, with restarts and gaps
  (`aggregation.md` 5). Up to 2.x the gauges reported a total per sample.

## 2.0 (2025-10)

- `units` lines can appear inside a file and set only the quantities they
  name (`files.md` 4.2). Sensors are swapped in the field without a new
  upload.
