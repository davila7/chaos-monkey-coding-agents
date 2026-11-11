# References

This note covers references from one value to another and when they are
expanded.

## 1. Where references apply

1.1 References are expanded in unquoted and double-quoted values
(`syntax.md` 5.2, 5.6). Single-quoted values are never expanded
(`syntax.md` 5.3).

## 2. Reference syntax

2.1 A reference is `${NAME}`. NAME is either a key (`${host}`) or a section
name, a dot and a key (`${database.host}`, `${db.replica.host}`), with the
characters `syntax.md` 3.1 and 4.3 allow.

2.2 `$$` writes one `$` and starts no reference.

2.3 A `$` that is followed by anything other than `{` or `$` is kept as it is:
`cost $5` stays `cost $5`.

2.4 Text is read from left to right, and a `$$` pair is taken before a
reference: `$$${a}` is a `$` followed by the value of `a`.

2.5 A `${` without a closing `}`, or a NAME that is not a key or a section
name and a key, is an `InterpolationError`.

## 3. Which value a reference names

3.1 When NAME holds a dot, the section is everything before the last dot and
the key everything after it. `${db.replica.host}` names the key `host` of the
section `db.replica`. The section part is not case-sensitive (`syntax.md`
3.2); the key is.

3.2 When NAME holds no dot, the key is looked up in the section of the value
that holds the reference. When that section has no such key, it is looked up
in the section `defaults`.

    [defaults]
    root = /srv
    [paths]
    data = ${root}/data      /srv/data, from [defaults]
    cache = ${data}/cache    /srv/data/cache, from [paths]

3.3 A reference may name a key of a template section (`syntax.md` 3.6).

3.4 A reference that names no key is an `InterpolationError`.

## 4. When references are expanded

4.1 References are expanded after the config and all of its shared files have
been read and merged (`overview.md` 3.3, 3.4). A reference therefore sees the
final value of the key it names: whether that key is assigned before or after
the reference, in the same file or in another one, and however often it is
assigned again.

    [server]
    url = https://${host}/   https://edge.internal/
    host = old.internal
    host = edge.internal

4.2 A value that refers to its own key refers to its own final value. It does
not extend an earlier value of the key; it is a cycle:

    [server]
    path = /usr/bin
    path = ${path}:/opt/bin  InterpolationError: reference cycle

4.3 The value a reference names is expanded first, and its result is
inserted as text. Inserted text is not read again for references: a
single-quoted value `'${x}'` inserted into another value stays `${x}`.

4.4 A chain of references that comes back to a value it started from is an
`InterpolationError`.

4.5 Expansion gives text. The text is converted to the key's type afterwards
(`types.md`), so `port = ${base_port}` is an int when the schema says `port`
is one.

4.6 Every value of a section that is written (`output.md` 2.3) is expanded.
A value of a template section is expanded only when another value refers to
it.
