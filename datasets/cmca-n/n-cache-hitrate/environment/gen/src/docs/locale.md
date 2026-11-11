# Locale negotiation

The catalog has text in the locales listed in `locales`. A request gets one
of them, chosen from its `Accept-Language` header; the cache key carries the
chosen locale (`cache.md` 2.2), so every request that gets the same locale
shares the entry.

## 1. Reading the header

The header is a comma separated list of language ranges, each optionally
followed by `;q=<weight>`. Ranges are compared without regard to case. A
range without a weight has weight 1; a range with weight 0, or with a weight
that is not a number, is dropped. The remaining ranges are taken from the
highest weight to the lowest, and ranges of equal weight in the order they
appear. A missing or empty header has no ranges.

## 2. Choosing the locale

For each range in that order:

1. `*` gives `default_locale`.
2. A range equal to a supported locale gives that locale.
3. Otherwise, a supported locale whose primary subtag (the part before the
   first `-`) equals the range's primary subtag gives that locale; when
   several do, the first in `locales` wins.

The first range that gives a locale decides. When none does, the request gets
`default_locale`. The result is always spelled as in `locales`: with
`locales = ["en", "es", "pt-BR"]`, `en-GB` gives `en`, `pt-PT` gives `pt-BR`,
`PT-br` gives `pt-BR`, and `it-IT,it;q=0.9` gives `en` when `en` is the
default.

Examples with `locales = ["en", "en-GB", "fr"]` and `default_locale = "en"`:

| Header | Locale |
|---|---|
| `en-GB,en;q=0.8` | `en-GB` |
| `en-AU` | `en` |
| `fr-CA;q=0.4, de;q=0.9` | `fr` |
| `de, *;q=0.1` | `en` |
| `fr;q=0, en-GB;q=0.2` | `en-GB` |
