"""Records each event fxh sends on stdin to $LOG and changes nothing."""
import json, os, sys

event = json.load(sys.stdin)
with open(os.environ["LOG"], "a") as f:
    f.write(json.dumps(event) + "\n")
