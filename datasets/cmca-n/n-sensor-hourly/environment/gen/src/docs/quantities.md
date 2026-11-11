# Quantities and units

## 1. Quantities

| Name | Quantity | Canonical unit | Unit name |
|---|---|---|---|
| `temp` | air temperature | degrees Celsius | `degC` |
| `rh` | relative humidity | percent | `pct` |
| `pres` | station pressure | hectopascal | `hPa` |
| `wspd` | wind speed | metres per second | `ms` |
| `wdir` | wind direction, where the wind comes from, clockwise from north | degrees | `deg` |
| `rain` | precipitation counter (`aggregation.md` 5) | millimetres | `mm` |

Every value in the hourly file is in the canonical unit.

## 2. Units and conversions

2.1 A `units` line (`files.md` 4.2) can give a quantity any unit of its row
below. The conversion to the canonical unit is exact as written.

| Quantity | Unit name | To the canonical unit |
|---|---|---|
| `temp` | `degC` | as written |
| `temp` | `degF` | (value - 32) * 5 / 9 |
| `temp` | `K` | value - 273.15 |
| `rh` | `pct` | as written |
| `rh` | `frac` | value * 100 |
| `pres` | `hPa` | as written |
| `pres` | `kPa` | value * 10 |
| `pres` | `inHg` | value * 33.8638866667 |
| `pres` | `mmHg` | value * 1.33322387415 |
| `wspd` | `ms` | as written |
| `wspd` | `kmh` | value / 3.6 |
| `wspd` | `kn` | value * 1852 / 3600 |
| `wspd` | `mph` | value * 0.44704 |
| `wdir` | `deg` | as written |
| `rain` | `mm` | as written |
| `rain` | `tips:S` | value * S, where S is the millimetres per tip of the gauge, for example `tips:0.2` |

2.2 Unit names are case sensitive.

## 3. Valid ranges

3.1 After conversion to the canonical unit, a value outside its range is
treated as missing (`files.md` 6.3). The bounds belong to the range.

| Quantity | Lowest | Highest |
|---|---|---|
| `temp` | -50 | 60 |
| `rh` | 0 | 100 |
| `pres` | 870 | 1085 |
| `wspd` | 0 | 60 |
| `wdir` | 0 | 360 |
| `rain` | 0 | 5000 |

3.2 Ranges are checked on the converted value, never on the value as
written: 288.4 K is a valid temperature, 85 degC is not.

3.3 A direction of 360 is north, the same as 0.

3.4 A wind speed of exactly 0 is calm. Calm samples have a direction value
that means nothing (`aggregation.md` 4).
