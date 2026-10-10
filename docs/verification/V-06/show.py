import json,sys,os
d=sys.argv[1]
ev=[json.loads(l) for l in open(d+'/tt/events.jsonl')] if os.path.exists(d+'/tt/events.jsonl') else []
print(os.path.basename(d), [(e['decision'],e.get('type'),e['tool_name']) for e in ev])
if not os.path.exists(d+'/requests.jsonl'): print('  no requests'); sys.exit()
last=None
for l in open(d+'/requests.jsonl'): last=json.loads(l)['body']
for m in last['messages']:
  if isinstance(m['content'],list):
    for c in m['content']:
      if c['type']=='tool_result': print('  ->', json.dumps({k:c[k] for k in ('content','is_error') if k in c})[:500])
