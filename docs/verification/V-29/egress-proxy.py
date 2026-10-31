import asyncio,sys,time,os
LOG=sys.argv[1]; UP=os.environ.get("UPSTREAM")  # host:port of session proxy, or None for direct
async def pipe(r,w):
    try:
        while (b:=await r.read(65536)): w.write(b); await w.drain()
    except Exception: pass
    finally: w.close()
async def handle(r,w):
    line=(await r.readline()).decode(errors="replace")
    while (await r.readline()) not in (b"\r\n",b""): pass
    parts=line.split()
    open(LOG,"a").write(f"{time.time():.0f} {line.strip()}\n")
    if len(parts)<2 or parts[0]!="CONNECT": w.close(); return
    host,port=parts[1].rsplit(":",1)
    try:
        if UP:
            uh,up=UP.split(":"); ur,uw=await asyncio.open_connection(uh,int(up))
            uw.write(f"CONNECT {parts[1]} HTTP/1.1\r\nHost: {parts[1]}\r\n\r\n".encode()); await uw.drain()
            while (await ur.readline()) not in (b"\r\n",b""): pass
        else:
            ur,uw=await asyncio.open_connection(host,int(port))
    except Exception as e:
        open(LOG,"a").write(f"  fail {e}\n"); w.close(); return
    w.write(b"HTTP/1.1 200 OK\r\n\r\n"); await w.drain()
    await asyncio.gather(pipe(r,uw),pipe(ur,w))
async def main():
    s=await asyncio.start_server(handle,"0.0.0.0",3128)
    async with s: await s.serve_forever()
asyncio.run(main())
