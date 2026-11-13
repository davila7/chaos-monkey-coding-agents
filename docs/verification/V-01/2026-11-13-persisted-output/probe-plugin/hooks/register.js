export const register = (on) => {
  on('tool.call', async ($, e, next) => {
    const res = await next(e);
    const mode = (await $.process.run(['cat', '/work/mode'], { stdin: '', timeoutMs: 2000 })).stdout.trim();
    const r = res.result;
    const brief = JSON.stringify({ mode, keys: r && typeof r === 'object' ? Object.keys(r) : typeof r, stdoutLen: r?.stdout?.length, head: typeof r === 'string' ? r.slice(0, 200) : r?.stdout?.slice(0, 120), path: r?.persistedOutputPath, size: r?.persistedOutputSize, isError: res.isError });
    await $.process.run(['sh', '-c', 'cat >> /work/out/probe.jsonl'], { stdin: brief + '\n', timeoutMs: 2000 });
    if (!r || typeof r !== 'object' || !r.persistedOutputPath) return res;
    const { persistedOutputPath: p, persistedOutputSize: _s, ...rest } = r;
    if (mode === 'pass') return res;
    if (mode === 'keep-empty') return { result: { ...r, stdout: '' } };
    if (mode === 'drop-empty') return { result: { ...rest, stdout: '' } };
    if (mode === 'drop-small') return { result: { ...rest, stdout: 'SMALL-REPLACED' } };
    if (mode === 'drop-mid') return { result: { ...rest, stdout: 'M'.repeat(Number(await (async()=>31000)())) } };
    if (mode === 'drop-big') return { result: { ...rest, stdout: 'B'.repeat(45000) } };
    if (mode === 'keep-small') {
      await $.process.run(['sh', '-c', `cat > ${p}`], { stdin: 'FILE-REWRITTEN\n', timeoutMs: 2000 });
      return { result: { ...r, stdout: 'KEEP-SMALL', persistedOutputSize: 15 } };
    }
    if (mode === 'keep-big') {
      const big = 'K'.repeat(41000);
      await $.process.run(['sh', '-c', `cat > ${p}`], { stdin: big, timeoutMs: 2000 });
      return { result: { ...r, stdout: big, persistedOutputSize: big.length } };
    }
    return res;
  });
};
