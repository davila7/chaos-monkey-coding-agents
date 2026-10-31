#!/bin/sh
f=/hooklog/$(date +%s%N)-$1.json
cat > "$f"
env | cut -d= -f1 | sort | tr '\n' ' ' > "$f.env"
exit 0
