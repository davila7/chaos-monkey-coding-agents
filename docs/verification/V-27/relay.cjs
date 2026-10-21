// Forwards 127.0.0.1:8787 in the agent container to the stub on the Docker host.
const net = require('net');
const [host, port] = (process.env.STUB_ADDR || '172.17.0.1:8787').split(':');
net.createServer((c) => {
  const up = net.connect(Number(port), host);
  c.pipe(up).pipe(c);
  c.on('error', () => up.destroy());
  up.on('error', () => c.destroy());
}).listen(8787, '127.0.0.1');
