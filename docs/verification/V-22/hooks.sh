H='{"hooks":{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo pre >> /out/hook-fired"}]}],"PostToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo post >> /out/hook-fired"}]}]}}'
mkdir -p /tmp/h/.fx /tmp/h/.claude /w/.fx /w/.claude
for f in /tmp/h/.fx/settings.json /tmp/h/.claude/settings.json /w/.fx/settings.json /w/.claude/settings.json /w/.fx.json; do echo "$H" > $f; done
sh /p/run.sh
if [ -e /out/hook-fired ]; then echo "hook fired: $(cat /out/hook-fired)"; else echo "no hook fired"; fi
