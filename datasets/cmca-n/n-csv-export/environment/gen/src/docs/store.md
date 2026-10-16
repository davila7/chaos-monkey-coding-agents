# The store

## 1. Layout

A store is a directory. Each collection is a subdirectory holding a
`schema.json` and one or more part files:

    store/
      customers/
        schema.json
        part-0001.jsonl
        part-0002.jsonl
        ...
      orders/
        ...

A subdirectory without `schema.json` is not a collection. Collection names
are the subdirectory names.

## 2. Part files

2.1 Part files are named `part-NNNN.jsonl` and are read in the order of their
names. Each non-empty line is one JSON object. Blank lines are skipped.

2.2 A line is either a **record** (an object holding the collection's fields)
or a **delete line**: an object with the single key `$delete` whose value is
the key of a record, for example `{"$delete": 500123}`.

2.3 Part files are written by other systems in append order; a later part may
change records of an earlier part (section 4).

## 3. Schemas and values

3.1 `schema.json` has the collection name, the name of the key field and the
list of fields:

    {
      "collection": "orders",
      "key": "id",
      "fields": [
        {"name": "id", "type": "int"},
        {"name": "total", "type": "decimal", "scale": 2},
        {"name": "address.city", "type": "string", "nullable": true}
      ]
    }

3.2 A field name is a dotted path into the record: `address.city` is the
`city` key of the object under `address`. When any step of the path is
missing, the value is missing.

3.3 Types and their JSON form:

| Type | JSON form | Python value (`tally.store.values.typed`) |
|---|---|---|
| `string` | string | `str` |
| `int` | number without fraction | `int` |
| `decimal` | string `-?digits.digits` with exactly `scale` fraction digits | `decimal.Decimal` |
| `bool` | `true` / `false` | `bool` |
| `date` | string `YYYY-MM-DD` | `datetime.date` |
| `datetime` | string `YYYY-MM-DDTHH:MM:SSZ` (UTC) | `datetime.datetime`, naive, UTC |

Decimals are kept as strings in the files so that no value ever passes
through binary floating point.

3.4 A missing value and JSON `null` both mean null. Only fields marked
`nullable` may be null.

## 4. Store order

4.1 The live records of a collection and their order (the **store order**)
come from reading the part files line by line, in order, and applying each
line:

* a record whose key is not live is added at the end;
* a record whose key is live replaces that record **in its place**: the new
  version keeps the position of the record it replaces;
* a delete line removes the live record with that key, if any. A record with
  that key that comes later is added at the end again.

4.2 `Collection.records()` (`tally/store/store.py`) yields the live records in
store order. Commands use it and never read part files themselves; the line
order of the part files is not the store order.

## 5. Validation

`python -m tally validate` checks every live record of every collection
against its schema: types, scale of decimals, nullability and unique keys.
The store in this repository validates without problems.
