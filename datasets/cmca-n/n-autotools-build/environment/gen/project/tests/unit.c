#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <isodur/isodur.h>

static int failures, count;

static void expect_format(const char *in, int style, const isodur_units *u, const char *want)
{
  isodur_t d;
  char buf[256] = "";
  int rc = isodur_parse(in, &d);

  if (rc == ISODUR_OK)
    rc = isodur_format(&d, style, u, buf, sizeof buf);
  count++;
  if (rc != ISODUR_OK || strcmp(buf, want) != 0) {
    printf("not ok %d - %s style %d: got \"%s\" (%s), expected \"%s\"\n", count, in, style, buf, isodur_strerror(rc), want);
    failures++;
  } else {
    printf("ok %d - %s style %d\n", count, in, style);
  }
}

static void expect_error(const char *in, int want)
{
  isodur_t d;
  int rc = isodur_parse(in, &d);

  count++;
  if (rc != want) {
    printf("not ok %d - %s: got %d, expected %d\n", count, in, rc, want);
    failures++;
  } else {
    printf("ok %d - %s rejected\n", count, in);
  }
}

static void expect_ms(const char *in, long long want)
{
  isodur_t d;
  int rc = isodur_parse(in, &d);

  count++;
  if (rc != ISODUR_OK || isodur_total_ms(&d) != want) {
    printf("not ok %d - %s: total %lld, expected %lld\n", count, in, rc ? -1 : isodur_total_ms(&d), want);
    failures++;
  } else {
    printf("ok %d - %s total\n", count, in);
  }
}

int main(void)
{
  const char *dir = getenv("DATA");
  char path[4096], buf[256];
  isodur_units *en, *de;
  isodur_t d;
  int err;

  if (strcmp(isodur_version(), ISODUR_VERSION_STRING) != 0) {
    printf("not ok - library %s, header %s\n", isodur_version(), ISODUR_VERSION_STRING);
    return 1;
  }

  expect_format("P1Y2M3W4DT5H6M7S", ISODUR_STYLE_ISO, NULL, "P1Y2M3W4DT5H6M7S");
  expect_format("1h30m", ISODUR_STYLE_ISO, NULL, "PT1H30M");
  expect_format("PT0.5S", ISODUR_STYLE_SHORT, NULL, "0.5s");
  expect_format("PT1,25S", ISODUR_STYLE_ISO, NULL, "PT1.25S");
  expect_format("  2d 4h  ", ISODUR_STYLE_SHORT, NULL, "2d4h");
  expect_format("1500ms", ISODUR_STYLE_ISO, NULL, "PT1.5S");
  expect_format("P0D", ISODUR_STYLE_ISO, NULL, "PT0S");
  expect_format("PT0S", ISODUR_STYLE_SHORT, NULL, "0s");
  expect_format("2mo1w", ISODUR_STYLE_ISO, NULL, "P2M1W");

  expect_error("", ISODUR_ESYNTAX);
  expect_error("P", ISODUR_ESYNTAX);
  expect_error("PT", ISODUR_ESYNTAX);
  expect_error("P1DT", ISODUR_ESYNTAX);
  expect_error("PT1.5H", ISODUR_ESYNTAX);
  expect_error("P1M1Y", ISODUR_ESYNTAX);
  expect_error("1m1h", ISODUR_ESYNTAX);
  expect_error("1.5h", ISODUR_ESYNTAX);
  expect_error("p1d", ISODUR_ESYNTAX);
  expect_error("P100000000D", ISODUR_ERANGE);

  expect_ms("P1Y", 365LL * 86400000);
  expect_ms("P1M", 30LL * 86400000);
  expect_ms("1w1d1h1m1s1ms", 8LL * 86400000 + 3661001);
  expect_ms("PT0.0004S", 0);

  if (isodur_from_ms(90061500, &d) != ISODUR_OK
      || isodur_format(&d, ISODUR_STYLE_ISO, NULL, buf, sizeof buf) != ISODUR_OK
      || strcmp(buf, "P1DT1H1M1.5S") != 0) {
    printf("not ok - from_ms: %s\n", buf);
    failures++;
  }

  if (!dir) {
    printf("not ok - DATA is not set\n");
    return 1;
  }
  snprintf(path, sizeof path, "%s/units.tsv", dir);
  en = isodur_units_load(path, "en", &err);
  de = isodur_units_load(path, "de", &err);
  if (!en || !de) {
    printf("not ok - cannot load %s: %s\n", path, isodur_strerror(err));
    return 1;
  }
  expect_format("PT1H30M", ISODUR_STYLE_LONG, en, "1 hour and 30 minutes");
  expect_format("P2DT1M1S", ISODUR_STYLE_LONG, en, "2 days, 1 minute and 1 second");
  expect_format("PT1.5S", ISODUR_STYLE_LONG, en, "1.5 seconds");
  expect_format("PT0S", ISODUR_STYLE_LONG, en, "0 seconds");
  expect_format("P1W3D", ISODUR_STYLE_LONG, de, "1 Woche und 3 Tage");
  if (isodur_units_load(path, "xx", &err) || err != ISODUR_ENOLANG) {
    printf("not ok - unknown language accepted\n");
    failures++;
  }
  isodur_units_free(en);
  isodur_units_free(de);

  printf("%d checks, %d failures\n", count, failures);
  return failures ? 1 : 0;
}
