# stockroom: overview

`stockroom` keeps stock for small warehouses: the item catalog, the bin
layout and where incoming pallets go, stock movements by lot, reorder
suggestions and review dates, freight quotes from carrier rate tables, and
the CSV reports built from all of these. It is a library; callers build the
objects and call the functions. It uses only the Python standard library.

| Note | Covers |
|---|---|
| `settings.md` | the settings table, overrides, units and rounding |
| `catalog.md` | item records and the catalog |
| `bins.md` | bin codes, the layout, walking cost, putaway |
| `stock.md` | the ledger, lots, aging, reorder points, review dates |
| `rates.md` | carrier rate tables, quotes, the table cache |
| `exports.md` | CSV exports and the standard files |
| `testing.md` | the unit tests, the CI runner, its logs, triage of failures |
| `changelog.md` | what changed between releases |

## 1. Modules

| Module | Role |
|---|---|
| `stockroom.clock` | the current time and the business date |
| `stockroom.settings` | built-in settings and overrides |
| `stockroom.units` | weights and lengths |
| `stockroom.catalog` | items |
| `stockroom.bins` | bins, layout, putaway |
| `stockroom.ledger` | movements and lots |
| `stockroom.reorder` | demand, reorder points, suggestions, reviews |
| `stockroom.rates` | rate tables and quotes |
| `stockroom.export` | CSV report files |
| `stockroom.reports` | the standard reports |
| `stockroom.errors` | the error classes |

## 2. Conventions

2.1 Weights are whole grams and lengths whole millimetres inside the package.
Other units appear only where a value is shown or read (`settings.md` 3).

2.2 Money is whole cents of the currency of the rate table it comes from.

2.3 Every error the package raises on purpose is a subclass of
`stockroom.errors.StockroomError`. Callers may rely on the subclass; messages
are for people and may change.

2.4 A function returns the same result for the same arguments, the same
settings and the same current time, whatever was called before it in the same
process, whatever the order of the calls, and whatever the process
environment holds besides `STOCKROOM_NOW` (section 4). In particular results
do not depend on `PYTHONHASHSEED`, on the timezone of the process (`TZ`) or on
files left in the temporary directory by earlier calls.

2.5 The package never changes process-wide state that it does not own: it
does not set environment variables, change the working directory, change the
process timezone or install signal handlers.

## 3. Dates

3.1 Every date the package stores or prints is a calendar date in UTC. The
**business date** is the UTC date of the current time: a call made at
2027-03-14T23:30Z belongs to 2027-03-14 everywhere in the world, and one made
at 2027-03-15T00:10Z to 2027-03-15.

3.2 Functions that take an optional date (`as_of`, `on`, `last`) use the
business date when it is left out.

3.3 Dates are written `YYYY-MM-DD`. Times are ISO 8601 with a `Z` or an
offset; a time without one is refused.

## 4. The current time

4.1 `stockroom.clock.now()` is the only source of the current time in the
package. It returns an aware datetime in UTC.

4.2 When the environment variable `STOCKROOM_NOW` holds an ISO 8601 time with
a `Z` or an offset, `now()` returns that time (converted to UTC) for the whole
process. The CI runner sets it for every run (`testing.md` 2.3), so a run can
be repeated with the same clock.

4.3 `stockroom.clock.today()` returns the business date (3.1).

## 5. Versions

The release is `stockroom.__version__`. The changelog lists the changes of
each release.
