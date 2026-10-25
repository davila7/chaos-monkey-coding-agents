"""The candidate dates of one period of a rule (rules.md section 4)."""

from datetime import date, timedelta

from .parse import Rule


def days_in_month(year: int, month: int) -> int:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return (nxt - date(year, month, 1)).days


def shift_month(year: int, month: int, n: int) -> tuple[int, int]:
    i = year * 12 + (month - 1) + n
    return i // 12, i % 12 + 1


def week_start(d: date, wkst: int) -> date:
    return d - timedelta(days=(d.weekday() - wkst) % 7)


def _monthdays(year: int, month: int, monthdays) -> set[date]:
    size = days_in_month(year, month)
    out = set()
    for n in monthdays:
        day = n if n > 0 else size + n + 1
        if 1 <= day <= size:
            out.add(date(year, month, day))
    return out


def _weekdays(year: int, month: int, byday) -> set[date]:
    size = days_in_month(year, month)
    out = set()
    for n, wd in byday:
        first = date(year, month, 1)
        all_days = [first + timedelta(days=i) for i in range((wd - first.weekday()) % 7, size, 7)]
        if n == 0:
            out.update(all_days)
        elif n > 0 and n <= len(all_days):
            out.add(all_days[n - 1])
        elif n < 0 and -n <= len(all_days):
            out.add(all_days[n])
    return out


def _month(rule: Rule, year: int, month: int, start: date) -> set[date]:
    if rule.bymonthday and rule.byday:
        return _monthdays(year, month, rule.bymonthday) & _weekdays(year, month, rule.byday)
    if rule.bymonthday:
        return _monthdays(year, month, rule.bymonthday)
    if rule.byday:
        return _weekdays(year, month, rule.byday)
    return _monthdays(year, month, (start.day,))


def _limit(rule: Rule, d: date) -> bool:
    if rule.bymonth and d.month not in rule.bymonth:
        return False
    if rule.bymonthday and d not in _monthdays(d.year, d.month, rule.bymonthday):
        return False
    if rule.byday and d.weekday() not in {wd for _, wd in rule.byday}:
        return False
    return True


def _setpos(rule: Rule, days: list[date]) -> list[date]:
    if not rule.bysetpos:
        return days
    out = set()
    for n in rule.bysetpos:
        if n > 0 and n <= len(days):
            out.add(days[n - 1])
        elif n < 0 and -n <= len(days):
            out.add(days[n])
    return sorted(out)


def period_start(rule: Rule, start: date, k: int) -> date:
    """The first day of the k-th period counted from the one holding DTSTART."""
    step = k * rule.interval
    if rule.freq == "DAILY":
        return start + timedelta(days=step)
    if rule.freq == "WEEKLY":
        return week_start(start, rule.wkst) + timedelta(weeks=step)
    if rule.freq == "MONTHLY":
        return date(*shift_month(start.year, start.month, step), 1)
    return date(start.year + step, 1, 1)


def period_dates(rule: Rule, start: date, k: int) -> list[date]:
    first = period_start(rule, start, k)
    if rule.freq == "DAILY":
        days = [first] if _limit(rule, first) else []
    elif rule.freq == "WEEKLY":
        weekdays = {wd for _, wd in rule.byday} or {start.weekday()}
        days = [first + timedelta(days=i) for i in range(7)]
        days = [d for d in days if d.weekday() in weekdays and (not rule.bymonth or d.month in rule.bymonth)]
    elif rule.freq == "MONTHLY":
        if rule.bymonth and first.month not in rule.bymonth:
            return []
        days = sorted(_month(rule, first.year, first.month, start))
    else:
        if rule.bymonth:
            months = rule.bymonth
        elif rule.byday or rule.bymonthday:
            months = range(1, 13)
        else:
            months = (start.month,)
        found = set()
        for m in months:
            found |= _month(rule, first.year, m, start)
        days = sorted(found)
    return _setpos(rule, days)
