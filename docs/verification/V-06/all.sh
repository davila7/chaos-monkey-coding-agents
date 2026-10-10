#!/bin/bash
set -u
npm i -g -q opencode-ai@1.18.35 >/dev/null 2>&1
echo "opencode $(opencode --version), node $(node --version)"
/w/probe.sh read-err err read '{"filePath":"$WS/input.txt"}'
/w/probe.sh bash-deny deny bash '{"command":"cat input.txt","description":"show"}'
/w/probe.sh read-trunc trunc read '{"filePath":"$WS/input.txt"}'
/w/probe.sh glob-empty empty glob '{"pattern":"*.txt"}'
/w/probe.sh grep-trunc trunc grep '{"pattern":"line","path":"$WS"}'
/w/probe.sh edit-empty empty edit '{"filePath":"$WS/input.txt","oldString":"line two","newString":"line 2"}'
/w/probe.sh write-falsefail falsefail write '{"filePath":"$WS/out.txt","content":"hello"}'; echo "  out.txt exists: $(test -f /w/runs/write-falsefail/ws/out.txt && echo yes || echo no)"
/w/probe.sh read-missing trunc read '{"filePath":"$WS/nope.txt"}'
/w/probe.sh bash-clean none bash '{"command":"cat input.txt","description":"show"}'
/w/probe.sh broken-plugin deny bash '{"command":"cat input.txt","description":"show"}' file:///w/broken.js
