import json,sys,glob
P={"in":1.25e-6,"cached":0.15e-6,"out":4.25e-6}
tot=0
for f in sorted(glob.glob(sys.argv[1]+"/**/*.jsonl",recursive=True)):
    c=0
    for l in open(f):
        try: d=json.loads(l)
        except: continue
        if d.get("payload_type")=="run.usage":
            for m in d["payload"]["models"]:
                c+=(m["input_tokens"]-m["cached_tokens"])*P["in"]+m["cached_tokens"]*P["cached"]+m["output_tokens"]*P["out"]
    tot+=c; print(f"{c:.4f} {f}")
print(f"TOTAL {tot:.4f}")
