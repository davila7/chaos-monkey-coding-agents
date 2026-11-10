# Syntax

This note covers how a config or shared file is split into lines and how each
line is read. Includes are in `include.md`, references in `interp.md`.

## 1. Files

1.1 A config is the file `DATA/configs/<id>.conf`; its id is the file name
without `.conf`. A shared file is `DATA/shared/<name>`, where the name ends in
`.conf`. Both are read with the rules of this note.

1.2 Line numbers in error messages count physical lines from 1.

## 2. Lines

2.1 A file is split into physical lines at each line feed. A carriage return
at the end of a physical line is removed, and so are spaces and tabs at its
end.

2.2 A physical line whose last character (after 2.1) is a backslash continues
on the next physical line. The backslash is removed, the leading spaces and
tabs of the next line are removed, and the two are joined with nothing in
between. A logical line can continue over any number of physical lines. A
backslash at the end of the last line of a file is removed.

    tags = blue, \
           green        is read as   tags = blue, green
    path = /srv\
           /data        is read as   path = /srv/data

2.3 Continuations are joined before anything else is read, so a comment line
that ends with a backslash takes the next line into the comment.

2.4 A logical line that is empty or holds only spaces and tabs is skipped. So
is a logical line whose first character other than a space or tab is `#` or
`;`: a whole-line comment.

2.5 Every other logical line is a section header (section 3), a directive
(`include.md` section 1) or an assignment (section 4). A line that is none of
these is a `ParseError`.

## 3. Section headers

3.1 A section header is `[name]`. Spaces and tabs may stand between the
brackets and the name. A name is one or more parts separated by single dots,
and each part is one or more ASCII letters, digits, `_` or `-`: `server`,
`server.tls`, `edge-1.pool_a`.

3.2 Section names are not case-sensitive. A name is lowercased when it is
read, so `[Server]`, `[SERVER]` and `[ server ]` name the same section.

3.3 After the closing bracket a header may have only spaces and tabs,
optionally followed by a comment that starts with `#` or `;` after at least
one space or tab.

3.4 A section header may appear more than once, in one file or in several. Its
keys all belong to the one section.

3.5 Assignments before the first section header of a file belong to the
section `main`.

3.6 A section whose name starts with `_` is a template. Its values can be
referred to like any other (`interp.md`), but the section is not written
(`output.md` 2.3).

## 4. Assignments

4.1 An assignment is a key, a separator and a value.

4.2 The separator is the first `=` or `:` of the line, whichever comes first.
Everything before it, with surrounding spaces and tabs removed, is the key.
Everything after it is the value (section 5). Later `=` and `:` characters
belong to the value:

    url = https://edge.example:8443/   key url,  value https://edge.example:8443/
    dsn: pg://app@db:5432/main?ssl=on  key dsn,  value pg://app@db:5432/main?ssl=on
    opts=a=1;b=2                       key opts, value a=1;b=2

4.3 A key is one or more ASCII letters, digits, `_` or `-`. Keys are
case-sensitive and hold no dots. Any other key is a `ParseError`.

4.4 When a key is assigned more than once in a section, the last assignment
wins, wherever it stands: later in the same file, under a repeated header, or
in a shared file that is included later (`include.md` 2.3).

## 5. Values

5.1 The spaces and tabs around a value are removed. Its first character then
decides how it is read: `"` starts a double-quoted value, `'` a single-quoted
value, anything else an unquoted value. An empty value is the empty string.

5.2 A double-quoted value runs to the next `"` that is not escaped. Inside it
a backslash starts an escape:

| Escape | Gives |
|---|---|
| `\\` | a backslash |
| `\"` | a double quote |
| `\n` | a line feed |
| `\t` | a tab |
| `\$` | `$$`, which expansion writes as one `$` (`interp.md` 2.2) |

Any other character after a backslash, or a backslash at the end of the
value, is a `ParseError`. References in a double-quoted value are expanded.
Because `\$` stands for `$$`, `"\${HOME}"` is the text `${HOME}`, not a
reference.

5.3 A single-quoted value runs to the next `'`. It has no escapes and its
references are never expanded: `'${HOME}'` is the text `${HOME}`, and a
backslash is a backslash.

5.4 After the closing quote of a quoted value the line may hold only spaces
and tabs, optionally followed by a comment that starts with `#` after at
least one space or tab. A quoted value without its closing quote, or with
other text after it, is a `ParseError`.

5.5 In an unquoted value, an inline comment starts at a `#` that directly
follows a space or a tab, and runs to the end of the line. The comment and the
spaces and tabs before it are removed. A `#` that directly follows any other
character, or the separator, is part of the value. A `;` never starts an
inline comment:

    color = #336699            the value is empty (the # follows a space)
    color=#336699              the value is #336699
    docs = https://h/guide#ch2 the value is https://h/guide#ch2
    retry = 3   # attempts     the value is 3
    opts = a;b                 the value is a;b

5.6 References in an unquoted value are expanded (`interp.md`).
