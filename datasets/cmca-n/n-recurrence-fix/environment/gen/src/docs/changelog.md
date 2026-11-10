# Changelog

## 4.2.0

- Extra dates may come before the event start (`events.md` 4.3).
- The text view marks overridden instances.

## 4.1.0

- Zones south of the equator: daylight saving that starts late in one year and
  ends early in the next (`zones.md` 3.2).
- `UNTIL` accepts a UTC time as well as a date (`rules.md` 5.4, 5.5).

## 4.0.0

- COUNT is counted on the generated times, before excluded dates are taken
  out (`rules.md` 5.2). Up to 3.x the package counted the instances left after
  exclusion, so an excluded date made the rule produce one more instance; the
  calendar policy behind that rule is withdrawn (see
  `archive/2026-count-policy.md`).
- Skipped local times move forward by the length of the gap (`zones.md` 4.2).
- `WKST` is supported for weekly rules.

## 3.4.0

- Overrides can cancel an instance.
- The agenda listing `OUT/agenda.json`.
