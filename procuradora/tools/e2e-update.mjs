// Prueba de actualización: con la app ya "instalada" (service worker activo y caché llena), se publica una
// versión nueva en el servidor y se comprueba que el móvil la ve al reabrirla; y sin cobertura sigue arrancando.
// Uso: node tools/e2e-update.mjs
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { serve, CHROME } from './serve.mjs';
let marca = 'VERSION-VIEJA';
const { srv, port } = await serve(process.cwd(), (p, body) => p === '/index.html' ? Buffer.from(body.toString('utf8').replace("const VERSION = 'v", `const VERSION = '${marca} v`)) : body);
const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: 412, height: 915 }, locale: 'es-ES', isMobile: true, hasTouch: true });
const page = await ctx.newPage();
page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exitCode = 1; });
const version = () => page.evaluate(() => VERSION);
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForFunction(() => navigator.serviceWorker.controller !== null, null, { timeout: 15000 });
await page.fill('#bv-n', 'Carmen'); await page.click('#bv-ok');
if (!(await version()).includes('VERSION-VIEJA')) throw new Error('primera carga inesperada');
console.log('OK  primera visita sin recargas: ' + await version());
marca = 'VERSION-NUEVA';
await page.reload();
await page.waitForFunction(() => typeof VERSION !== 'undefined' && VERSION.includes('VERSION-NUEVA'), null, { timeout: 20000 });
console.log('OK  al reabrir con cobertura se ve la versión publicada');
await ctx.setOffline(true); srv.close();
await page.reload();
await page.waitForSelector('text=Aún no hay plazos', { timeout: 20000 });
console.log('OK  sin cobertura sigue arrancando con la copia guardada');
await browser.close();
