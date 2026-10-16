# The locale table

`locales/` holds one JSON file per locale, named after the locale
(`locales/de-DE.json`). `tally.fmt.locales.load_locale(name)` reads one entry;
`available()` lists the names.

## Keys

| Key | Meaning |
|---|---|
| `name` | the locale name, equal to the file name without `.json` |
| `decimal` | text between the integer digits and the fraction digits |
| `group` | text between digit groups of the integer part |
| `group_sizes` | list of group sizes, rightmost group first; the last size repeats (`docs/export.md`, section 7.3) |
| `min_grouping` | grouping applies only when the integer part has at least `group_sizes[0] + min_grouping` digits |
| `minus` | text written before a negative number |
| `date` | pattern for dates (`docs/export.md`, section 7.4) |
| `datetime` | pattern for datetimes |
| `true` / `false` | text for boolean values |

## Characters

Separators and signs are taken from the table exactly as written, and several
are not ASCII. Among the entries in the table:

- group separators include the no-break space (U+00A0), the narrow no-break
  space (U+202F) and the right single quotation mark (U+2019);
- `minus` is the hyphen-minus (U+002D) in most entries and the minus sign
  (U+2212) in others.

Never retype these characters; read them from the table.

## Adding a locale

Add a file with every key above. The tests check that every file in
`locales/` loads.
