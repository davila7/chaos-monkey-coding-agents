"""The value of an assignment: quoting, escapes and inline comments (syntax.md section 5)."""

from .errors import ParseError

# '\$' becomes '$$', which interpolation writes as one '$' (interp.md 2.2).
ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "$": "$$"}


def strip_comment(raw: str) -> str:
    """Removes an inline comment: a '#' right after a space or tab, and everything after it."""
    for i, c in enumerate(raw):
        if c == "#" and i > 0 and raw[i - 1] in " \t":
            return raw[:i]
    return raw


def _after_quote(rest: str, where: str) -> None:
    if rest.strip() and not (rest[0] in " \t" and rest.strip().startswith("#")):
        raise ParseError(f"{where}: text after the closing quote")


def parse_value(raw: str, where: str) -> tuple[str, bool]:
    """The value text and whether interpolation applies to it."""
    s = raw.strip()
    if s.startswith("'"):
        end = s.find("'", 1)
        if end < 0:
            raise ParseError(f"{where}: unterminated single-quoted value")
        _after_quote(s[end + 1:], where)
        return s[1:end], False
    if s.startswith('"'):
        out, i = [], 1
        while True:
            if i >= len(s):
                raise ParseError(f"{where}: unterminated double-quoted value")
            c = s[i]
            if c == '"':
                break
            if c == "\\":
                nxt = s[i + 1] if i + 1 < len(s) else ""
                if nxt not in ESCAPES:
                    raise ParseError(f"{where}: unknown escape \\{nxt}")
                out.append(ESCAPES[nxt])
                i += 2
                continue
            out.append(c)
            i += 1
        _after_quote(s[i + 1:], where)
        return "".join(out), True
    return strip_comment(raw).strip(), True
