// Servidor estático mínimo para las pruebas (sirve la carpeta actual).
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json' };
export function serve(root, hook) {
  const srv = createServer((req, res) => {
    let p = decodeURIComponent(req.url.split('?')[0]); if (p === '/') p = '/index.html';
    const f = join(root, p); if (!existsSync(f) || statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
    let body = readFileSync(f); if (hook) body = hook(p, body);
    res.writeHead(200, { 'content-type': types[extname(f)] || 'application/octet-stream', 'cache-control': 'no-cache' });
    res.end(body);
  });
  return new Promise(r => srv.listen(0, () => r({ srv, port: srv.address().port })));
}
export const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
