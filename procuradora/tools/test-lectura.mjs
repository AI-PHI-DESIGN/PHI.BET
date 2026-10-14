// Comprueba la lectura automática de PDF con documentos inventados que imitan los formatos reales:
// carátula de LexNET, diligencia del Tribunal de Instancia (GVA), auto penal sin plazo propio y escrito de la procuradora.
// Uso: node tools/test-lectura.mjs
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { serve, CHROME } from './serve.mjs';
const dir = mkdtempSync(join(tmpdir(), 'lectura-'));
const ESPERADO = {
  lexnet: { organo: 'Juzgado de Primera Instancia', procedimiento: 'Procedimiento Ordinario 123/2026', cliente: 'Maria Garcia Lopez contra Banco Ejemplo S.A.', resolucion: 'Diligencia de Ordenación', plazo: 5, actuacion: 'Alegaciones', recepcion: '2026-10-05' },
  'gva-subsanar': { organo: 'Sección Civil y de Instrucción del Tribunal de Instancia de Picassent. Plaza nº 2', procedimiento: 'Juicio verbal (250.2) 321/2026', nig: '4619441120260009999', cliente: 'Talleres Ejemplo S.L. contra Muebles Ficticios S.A.', resolucion: 'Diligencia de Ordenación', plazo: 2, actuacion: 'Subsanar' },
  'gva-auto': { organo: 'Sección de lo Penal del Tribunal de Instancia de Valencia. Plaza nº 20', procedimiento: 'Procedimiento abreviado 999/2026', cliente: 'Luis Ejemplo Garcia contra Ana Prueba Lopez y Marta Ficticia Ruiz', resolucion: 'Auto', plazo: 3, recursos: 'Recurso de reforma:3,Recurso de apelación:5' },
  escrito: { tipoDoc: 'escrito', organo: 'Sección Civil y de Instrucción del Tribunal de Instancia de Quart de Poblet. Plaza nº 2', procedimiento: 'Juicio Verbal (250.1.14) nº 111/2025', cliente: 'Lucia Cliente Ficticia', plazo: undefined },
};
const { srv, port } = await serve(process.cwd());
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage();
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForFunction(() => typeof extraer === 'function');
await page.evaluate(() => { const i = document.createElement('input'); i.type = 'file'; i.id = 'tst'; document.body.append(i); });
let fallos = 0;
for (const [modelo, esp] of Object.entries(ESPERADO)) {
  const f = join(dir, modelo + '.pdf'); execFileSync('node', ['tools/make-test-pdf.mjs', f, modelo]);
  await page.setInputFiles('#tst', f);
  const x = await page.evaluate(async () => extraer(await textoPDF(document.querySelector('#tst').files[0])));
  const got = { ...x, plazo: x.plazo && x.plazo.cantidad, recepcion: x.recepcion && x.recepcion.fecha, recursos: x.recursos && x.recursos.map(r => r.nombre + ':' + r.cantidad).join(',') };
  for (const [k, v] of Object.entries(esp)) {
    const ok = v === undefined ? got[k] === undefined : String(got[k] || '').includes(String(v));
    if (!ok) fallos++;
    console.log(`${ok ? 'OK ' : 'MAL'} ${modelo} · ${k}: ${JSON.stringify(got[k])}${ok ? '' : '  (esperado ' + JSON.stringify(v) + ')'}`);
  }
}
await browser.close(); srv.close();
if (fallos) { console.error(fallos + ' datos mal leídos'); process.exit(1); }
console.log('LECTURA OK');
