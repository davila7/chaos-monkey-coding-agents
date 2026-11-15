#include "internal.h"

const char *isodur_version(void)
{
  return ISODUR_VERSION_STRING;
}

const char *isodur_strerror(int err)
{
  switch (err) {
  case ISODUR_OK: return "ok";
  case ISODUR_ESYNTAX: return "invalid duration";
  case ISODUR_ERANGE: return "value out of range";
  case ISODUR_ENOMEM: return "out of memory";
  case ISODUR_EIO: return "cannot read unit table";
  case ISODUR_ETABLE: return "malformed unit table";
  case ISODUR_ENOLANG: return "unknown language";
  case ISODUR_ENOUNITS: return "no unit table";
  default: return "unknown error";
  }
}
