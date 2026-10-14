python3 /r/gen_exports.py /tmp/h --seed 73113 --data-only >/dev/null
python3 /r/agent-summarize.py /tmp/h/data /tmp/a.json; python3 /r/oracle.py /tmp/h/data /tmp/o.json
python3 - <<'P'
import json
a=json.load(open('/tmp/a.json'));o=json.load(open('/tmp/o.json'))
def diff(x,y,p=''):
  if isinstance(x,dict):
    for k in set(x)|set(y): diff(x.get(k),y.get(k),p+'.'+k)
  elif x!=y: print(p,'agent',x,'oracle',y)
diff(a,o)
P
