# Versions

Every version in the index, in a manifest and in a range follows this note.
`pinset.version.Version` implements it.

## 1. Text form

    version    = number "." number "." number [ "-" prerelease ] [ "+" build ]
    number     = "0" / nonzero *digit
    prerelease = pre-id *( "." pre-id )
    pre-id     = number / *digit letter-or-hyphen *( digit / letter-or-hyphen )
    build      = build-id *( "." build-id )
    build-id   = 1*( digit / letter-or-hyphen )

Digits are `0` to `9`, letters are ASCII `A` to `Z` and `a` to `z`. The three
numbers are the major, minor and patch numbers. Numeric prerelease
identifiers have no leading zeros (`rc.01` is not a version); build
identifiers may have them (`+001` is fine).

Examples: `0.4.0`, `2.10.3`, `3.0.0-rc.11`, `1.2.3-beta.x-1`,
`1.0.0-alpha+exp.sha-5114f85`, `4.1.7+20270114`.

## 2. Words

- A **prerelease** is a version with a prerelease part. A version without one
  is a plain version.
- The **release** of a version is its three numbers. `1.4.0-rc.2`,
  `1.4.0` and `1.4.0+linux` belong to the release `1.4.0`.
- **Build metadata** is the part after `+`.

## 3. Precedence

Versions are ordered by precedence. Two versions are compared like this:

1. Compare major, minor and patch numerically, in that order. The first
   difference decides.
2. With equal numbers, a plain version is higher than any prerelease:
   `1.4.0-rc.2 < 1.4.0`.
3. Two prereleases of the same release are compared identifier by identifier,
   from left to right, until one differs:
   - two identifiers made only of digits are compared numerically;
   - two other identifiers are compared character by character in ASCII order;
   - an identifier made only of digits is lower than any other identifier.
   If all identifiers are equal up to the length of the shorter prerelease,
   the one with more identifiers is higher.
4. Build metadata is ignored: `1.4.0+a` and `1.4.0+b` have the same
   precedence. Equality of versions means equal precedence.

So: `1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta <
1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0`.

## 4. Text kept as written

`Version.parse` keeps every identifier as written, and `str(version)` gives
the text back, build metadata included. Outputs that name an index release
print the text of the index file, not a normalised form (`output.md`).

## 5. History

- 1.0: three numbers only.
- 1.3: prereleases and build metadata in index files. Only an exact range
  chooses a prerelease (`ranges.md`, introduction), so precedence between
  two prereleases only decided the order of `show`.
- 2.0: ranges (`ranges.md`), which compare prereleases with each other; the
  resolver picks the highest version a range allows.
