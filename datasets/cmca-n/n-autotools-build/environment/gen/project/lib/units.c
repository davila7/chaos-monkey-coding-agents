#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "internal.h"

const char *const isodur__unit_keys[ISODUR__NUNITS] = {
  "year", "month", "week", "day", "hour", "minute", "second"
};

#define ALL_SEEN ((1u << (ISODUR__NUNITS + 1)) - 1)

/* Splits a table line into four tab-separated fields. Returns the number
   of fields, or -1 when a field is too long. */
static int fields(char *line, char *f[4])
{
  int n = 0, i;
  char *p = line;

  while (n < 4) {
    char *tab = strchr(p, '\t');
    f[n++] = p;
    if (!tab)
      break;
    *tab = '\0';
    p = tab + 1;
  }
  for (i = 0; i < n; i++)
    if (strlen(f[i]) >= ISODUR__WORD)
      return -1;
  return n;
}

static int listed(const char *buf, const char *lang)
{
  size_t n = strlen(lang);

  while (*buf) {
    const char *nl = strchr(buf, '\n');
    if ((size_t)(nl - buf) == n && strncmp(buf, lang, n) == 0)
      return 1;
    buf = nl + 1;
  }
  return 0;
}

static void chomp(char *s)
{
  size_t n = strlen(s);

  while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r'))
    s[--n] = '\0';
}

static int key_index(const char *key)
{
  int i;

  for (i = 0; i < ISODUR__NUNITS; i++)
    if (strcmp(key, isodur__unit_keys[i]) == 0)
      return i;
  return strcmp(key, "and") == 0 ? ISODUR__NUNITS : -1;
}

isodur_units *isodur_units_load(const char *path, const char *lang, int *err)
{
  FILE *fp;
  char line[256];
  isodur_units *u;
  int rc = ISODUR_OK, found = 0;

  if (!(fp = fopen(path, "r"))) {
    *err = ISODUR_EIO;
    return NULL;
  }
  if (!(u = calloc(1, sizeof *u))) {
    fclose(fp);
    *err = ISODUR_ENOMEM;
    return NULL;
  }
  while (rc == ISODUR_OK && fgets(line, sizeof line, fp)) {
    char *f[4];
    int n, k;

    chomp(line);
    if (!line[0] || line[0] == '#')
      continue;
    n = fields(line, f);
    if (n != 4 || (k = key_index(f[1])) < 0) {
      rc = ISODUR_ETABLE;
      break;
    }
    if (strcmp(f[0], lang) != 0)
      continue;
    found = 1;
    if (k == ISODUR__NUNITS) {
      strcpy(u->and_word, f[2]);
    } else {
      strcpy(u->one[k], f[2]);
      strcpy(u->other[k], f[3]);
    }
    u->seen |= 1u << k;
  }
  if (rc == ISODUR_OK && ferror(fp))
    rc = ISODUR_EIO;
  fclose(fp);
  if (rc == ISODUR_OK && !found)
    rc = ISODUR_ENOLANG;
  if (rc == ISODUR_OK && u->seen != ALL_SEEN)
    rc = ISODUR_ETABLE;
  if (rc != ISODUR_OK) {
    free(u);
    *err = rc;
    return NULL;
  }
  strcpy(u->lang, lang);
  *err = ISODUR_OK;
  return u;
}

void isodur_units_free(isodur_units *units)
{
  free(units);
}

int isodur_units_list(const char *path, char *buf, size_t size)
{
  FILE *fp;
  char line[256];
  size_t len = 0;
  int rc = ISODUR_OK;

  if (!buf || !size)
    return ISODUR_ERANGE;
  buf[0] = '\0';
  if (!(fp = fopen(path, "r")))
    return ISODUR_EIO;
  while (fgets(line, sizeof line, fp)) {
    char *f[4];
    size_t n;

    chomp(line);
    if (!line[0] || line[0] == '#')
      continue;
    if (fields(line, f) != 4 || key_index(f[1]) < 0) {
      rc = ISODUR_ETABLE;
      break;
    }
    if (listed(buf, f[0]))
      continue;
    n = strlen(f[0]);
    if (len + n + 1 >= size) {
      rc = ISODUR_ERANGE;
      break;
    }
    memcpy(buf + len, f[0], n);
    buf[len + n] = '\n';
    buf[len + n + 1] = '\0';
    len += n + 1;
  }
  fclose(fp);
  if (rc != ISODUR_OK)
    buf[0] = '\0';
  return rc;
}
