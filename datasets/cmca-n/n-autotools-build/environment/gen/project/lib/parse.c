#include <ctype.h>
#include <string.h>

#include "internal.h"

const char *isodur__skip_space(const char *s)
{
  while (*s && isspace((unsigned char)*s))
    s++;
  return s;
}

/* Digits with an optional fraction after '.' or ','. Digits past
   ISODUR_MAX_COMPONENT are still consumed so that a syntax error later in
   the text is reported before the range error. */
static int number(const char **pp, const char *end, long *whole, double *frac, int *has_frac)
{
  const char *p = *pp;
  long v = 0;
  int digits = 0, big = 0;

  while (p < end && *p >= '0' && *p <= '9') {
    if (!big) {
      v = v * 10 + (*p - '0');
      if (v > ISODUR_MAX_COMPONENT)
        big = 1;
    }
    p++;
    digits++;
  }
  if (!digits)
    return ISODUR_ESYNTAX;
  *frac = 0.0;
  *has_frac = 0;
  if (p < end && (*p == '.' || *p == ',')) {
    double scale = 0.1;
    int fd = 0;
    p++;
    while (p < end && *p >= '0' && *p <= '9') {
      if (fd < 9) {
        *frac += (*p - '0') * scale;
        scale /= 10.0;
      }
      p++;
      fd++;
    }
    if (!fd)
      return ISODUR_ESYNTAX;
    *has_frac = 1;
  }
  *pp = p;
  *whole = v;
  return big ? ISODUR_ERANGE : ISODUR_OK;
}

static void set(isodur_t *d, int unit, long v, double frac)
{
  switch (unit) {
  case ISODUR__YEAR: d->years = v; break;
  case ISODUR__MONTH: d->months = v; break;
  case ISODUR__WEEK: d->weeks = v; break;
  case ISODUR__DAY: d->days = v; break;
  case ISODUR__HOUR: d->hours = v; break;
  case ISODUR__MINUTE: d->minutes = v; break;
  default: d->seconds += (double)v + frac; break;
  }
}

static int parse_iso(const char *p, const char *end, isodur_t *d)
{
  static const char date_units[] = "YMWD";
  static const char time_units[] = "HMS";
  int in_time = 0, any = 0, any_time = 0, last = -1, range = 0;

  p++;
  while (p < end) {
    long v;
    double frac;
    int has_frac, rc, unit;
    const char *units, *u;

    if (*p == 'T') {
      if (in_time)
        return ISODUR_ESYNTAX;
      in_time = 1;
      last = -1;
      p++;
      continue;
    }
    rc = number(&p, end, &v, &frac, &has_frac);
    if (rc == ISODUR_ESYNTAX || p >= end)
      return ISODUR_ESYNTAX;
    units = in_time ? time_units : date_units;
    u = strchr(units, *p);
    if (!*p || !u || (int)(u - units) <= last)
      return ISODUR_ESYNTAX;
    last = (int)(u - units);
    unit = in_time ? ISODUR__HOUR + last : ISODUR__YEAR + last;
    if (has_frac && unit != ISODUR__SECOND)
      return ISODUR_ESYNTAX;
    if (rc == ISODUR_ERANGE)
      range = 1;
    set(d, unit, v, frac);
    any = 1;
    if (in_time)
      any_time = 1;
    p++;
  }
  if (!any || (in_time && !any_time))
    return ISODUR_ESYNTAX;
  return range ? ISODUR_ERANGE : ISODUR_OK;
}

/* Short form units in the order they must appear. */
static const char *const short_units[] = { "y", "mo", "w", "d", "h", "m", "s", "ms" };

static int short_unit(const char **pp, const char *end)
{
  const char *p = *pp;
  size_t n = 0;
  int i;

  while (p + n < end && p[n] >= 'a' && p[n] <= 'z')
    n++;
  for (i = 0; i < 8; i++) {
    if (strlen(short_units[i]) == n && strncmp(p, short_units[i], n) == 0) {
      *pp = p + n;
      return i;
    }
  }
  return -1;
}

static int parse_short(const char *p, const char *end, isodur_t *d)
{
  int last = -1, range = 0;

  while (p < end) {
    long v;
    double frac;
    int has_frac, rc, idx;

    rc = number(&p, end, &v, &frac, &has_frac);
    if (rc == ISODUR_ESYNTAX)
      return ISODUR_ESYNTAX;
    idx = short_unit(&p, end);
    if (idx < 0 || idx <= last)
      return ISODUR_ESYNTAX;
    last = idx;
    if (has_frac && idx != ISODUR__SECOND)
      return ISODUR_ESYNTAX;
    if (rc == ISODUR_ERANGE)
      range = 1;
    if (idx == 7)
      d->seconds += (double)v / 1000.0;
    else
      set(d, idx, v, frac);
    while (p < end && *p == ' ')
      p++;
  }
  if (last < 0)
    return ISODUR_ESYNTAX;
  if (d->seconds > (double)ISODUR_MAX_COMPONENT)
    range = 1;
  return range ? ISODUR_ERANGE : ISODUR_OK;
}

int isodur_parse(const char *text, isodur_t *out)
{
  isodur_t d;
  const char *p, *end;
  int rc;

  if (!text || !out)
    return ISODUR_ESYNTAX;
  memset(&d, 0, sizeof d);
  p = isodur__skip_space(text);
  end = p + strlen(p);
  while (end > p && isspace((unsigned char)end[-1]))
    end--;
  if (p == end)
    return ISODUR_ESYNTAX;
  rc = *p == 'P' ? parse_iso(p, end, &d) : parse_short(p, end, &d);
  if (rc == ISODUR_OK)
    *out = d;
  return rc;
}
