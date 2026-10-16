#!/bin/sh
# Usage: mkversion.sh VERSION_FILE > version.h
# Writes the version header to stdout. The version file holds MAJOR.MINOR.PATCH on its first line.
set -e
file=${1:?usage: mkversion.sh VERSION_FILE}
v=$(sed -n '1{s/[[:space:]]//g;p;}' "$file")
case $v in
    *[!0-9.]*|"") echo "mkversion.sh: bad version '$v' in $file" >&2; exit 1 ;;
esac
major=${v%%.*}
rest=${v#*.}
minor=${rest%%.*}
patch=${rest#*.}
cat <<EOF
/* Generated from VERSION by build-aux/mkversion.sh. Do not edit. */
#ifndef QS_VERSION_H
#define QS_VERSION_H

#define QS_VERSION "$v"
#define QS_VERSION_MAJOR $major
#define QS_VERSION_MINOR $minor
#define QS_VERSION_PATCH $patch

#endif
EOF
