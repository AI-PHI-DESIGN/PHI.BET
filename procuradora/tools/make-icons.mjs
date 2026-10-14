// Genera icons/icon-192.png e icons/icon-512.png sin dependencias (PNG RGBA + zlib de Node).
// Dibuja lo mismo que icons/icon.svg: fondo índigo, calendario blanco con franja rosa-violeta y un check.
import { deflateSync } from 'node:zlib';
import { writeFileSync } from 'node:fs';
const crcT = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = b => { let c = ~0; for (const x of b) c = crcT[(c ^ x) & 255] ^ (c >>> 8); return ~c >>> 0; };
const chunk = (t, d) => { const len = Buffer.alloc(4); len.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
function png(size, paint) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y++) { raw[y * (size * 4 + 1)] = 0; for (let x = 0; x < size; x++) { const [r, g, b, a] = paint(x + .5, y + .5, size); const o = y * (size * 4 + 1) + 1 + x * 4; raw[o] = r; raw[o + 1] = g; raw[o + 2] = b; raw[o + 3] = a; } }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const D1 = [58, 61, 134], D2 = [23, 24, 60], PK1 = [255, 138, 208], PK2 = [142, 91, 245], WHITE = [255, 255, 255], LILA = [201, 203, 255], INK = [74, 79, 214];
// distancia con signo a un rectángulo redondeado (unidades 0..512)
const rrect = (x, y, x0, y0, x1, y1, r) => { const cx = Math.min(Math.max(x, x0 + r), x1 - r), cy = Math.min(Math.max(y, y0 + r), y1 - r); const inX = x > x0 + r && x < x1 - r, inY = y > y0 + r && y < y1 - r; if (inX || inY) return Math.max(x0 - x, x - x1, y0 - y, y - y1); return Math.hypot(x - cx, y - cy) - r; };
const seg = (u, v, ax, ay, bx, by) => { const t = Math.max(0, Math.min(1, ((u - ax) * (bx - ax) + (v - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2))); return Math.hypot(u - (ax + t * (bx - ax)), v - (ay + t * (by - ay))); };
function paint(px, py, s) {
  const k = 512 / s, x = px * k, y = py * k, aa = d => Math.min(1, Math.max(0, .5 - d / k));
  const dBg = rrect(x, y, 0, 0, 512, 512, 112); if (dBg > k) return [0, 0, 0, 0];
  let col = mix(D1, D2, (x + y) / 1024);
  const dCal = rrect(x, y, 106, 126, 406, 402, 64);
  if (dCal < k) col = mix(col, y < 214 ? mix(PK1, PK2, (x - 106) / 300) : WHITE, aa(dCal));
  for (const x0 of [166, 310]) { const d = rrect(x, y, x0, 86, x0 + 36, 170, 18); if (d < k) col = mix(col, LILA, aa(d)); }
  const dChk = Math.min(seg(x, y, 184, 300, 236, 352), seg(x, y, 236, 352, 332, 248)) - 19;
  if (dChk < k) col = mix(col, INK, aa(dChk));
  return [...col, Math.round(255 * aa(dBg))];
}
for (const s of [192, 512]) writeFileSync(`icons/icon-${s}.png`, png(s, paint));
console.log('icons ok');
