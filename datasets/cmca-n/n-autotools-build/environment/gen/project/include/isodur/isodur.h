#ifndef ISODUR_H
#define ISODUR_H

#include <stddef.h>

#include <isodur/version.h>

#ifdef __cplusplus
extern "C" {
#endif

/* A duration as written: components are kept apart, never carried. Only
   seconds may hold a fraction. Every component is between 0 and
   ISODUR_MAX_COMPONENT. */
typedef struct {
  long years;
  long months;
  long weeks;
  long days;
  long hours;
  long minutes;
  double seconds;
} isodur_t;

#define ISODUR_MAX_COMPONENT 99999999L

enum {
  ISODUR_OK = 0,
  ISODUR_ESYNTAX = 1,
  ISODUR_ERANGE = 2,
  ISODUR_ENOMEM = 3,
  ISODUR_EIO = 4,
  ISODUR_ETABLE = 5,
  ISODUR_ENOLANG = 6,
  ISODUR_ENOUNITS = 7
};

enum {
  ISODUR_STYLE_ISO = 0,
  ISODUR_STYLE_SHORT = 1,
  ISODUR_STYLE_LONG = 2
};

typedef struct isodur_units isodur_units;

const char *isodur_version(void);
const char *isodur_strerror(int err);

/* ISO 8601 ("P1DT2H30M", "PT0.5S") or short form ("1d2h30m", "90s",
   "2h 15m", "1500ms"). Leading and trailing white space is ignored. */
int isodur_parse(const char *text, isodur_t *out);

/* Nominal length in milliseconds: a year is 365 days, a month 30 days. */
long long isodur_total_ms(const isodur_t *d);

/* Days, hours, minutes and seconds of a length in milliseconds. */
int isodur_from_ms(long long ms, isodur_t *out);

/* Writes d in the given style. ISODUR_STYLE_LONG needs a unit table. */
int isodur_format(const isodur_t *d, int style, const isodur_units *units, char *buf, size_t size);

/* Loads the unit words of one language from a unit table file. Returns
   NULL and sets *err on failure. */
isodur_units *isodur_units_load(const char *path, const char *lang, int *err);
void isodur_units_free(isodur_units *units);

/* Writes the languages of a unit table, one per line, in file order. */
int isodur_units_list(const char *path, char *buf, size_t size);

#ifdef __cplusplus
}
#endif

#endif
