# Includes

This note covers shared files: how a config pulls them in, where their values
apply, and how the document lists them.

## 1. The directive

1.1 A directive line is `%include NAME`, with one or more spaces or tabs
between the two words. NAME is the name of a file under `DATA/shared/`; it is
made of ASCII letters, digits, `_`, `-` and `.`, and ends in `.conf`. The
line may end with spaces or tabs and a comment that starts with `#`.

1.2 Any other line that starts with `%` is a `ParseError`.

1.3 A directive may appear anywhere in a config or a shared file: before the
first section header, between sections, or among the assignments of a
section.

## 2. Where values apply

2.1 The lines of a shared file are applied at the place of the directive, as
if they were written there, in their own order.

2.2 A shared file starts in the section `main`, like any file (`syntax.md`
3.5). Its section headers do not carry over to the file that includes it:
when the shared file ends, the including file goes on in the section it was in
before the directive.

    [api]
    threads = 4
    %include quota.conf      (quota.conf ends in its own [quota] section)
    retries = 3              still a key of [api]

2.3 A value from a shared file overrides the same key assigned earlier and is
overridden by the same key assigned later (`syntax.md` 4.4).

2.4 A config may include the same shared file more than once, directly or
through other shared files. The file is applied again at each directive, so
at that point its values win again over what was assigned in between.

## 3. Nesting and cycles

3.1 A shared file may include other shared files, to any depth.

3.2 A file that is still being applied cannot be included again until it
ends. A shared file that includes itself, directly or through other shared
files, is an `IncludeError`. Including a file again after it has ended is not
a cycle (2.4).

3.3 A directive that names a file that does not exist in `DATA/shared/` is an
`IncludeError`.

3.4 An error in a shared file is an error of the config that includes it. Its
message names the shared file.

## 4. The include list

4.1 The resolved document lists the shared files the config read
(`output.md` 2.1). Each file is listed once, in the order in which it was
first read, whether it was named by the config or by another shared file and
however often it was included.

    configs/edge.conf:  %include tls.conf      tls.conf includes base.conf
                        %include base.conf
    includes:           ["tls.conf", "base.conf"]
