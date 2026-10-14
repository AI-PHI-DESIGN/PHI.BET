// Prueba de punta a punta en un móvil simulado (412x915), con la fecha fijada al jueves 8 de octubre de 2026.
// Sube un PDF de LexNET de ejemplo, comprueba la lectura y el cálculo, guarda, avisa, exporta al calendario,
// mira el calendario y comprueba que los datos siguen tras recargar y sin conexión.
// Uso: node tools/e2e.mjs [dirCapturas]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { serve, CHROME } from './serve.mjs';
const OUT = process.argv[2] || 'shots'; mkdirSync(OUT, { recursive: true });
const pdf = join(OUT, 'notificacion-prueba.pdf');
execFileSync('node', ['tools/make-test-pdf.mjs', pdf]);
const { srv, port } = await serve(process.cwd());
const browser = await chromium.launch({ executablePath: CHROME });
const scheme = process.env.SCHEME || 'light';
const ctx = await browser.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, locale: 'es-ES', isMobile: true, hasTouch: true, acceptDownloads: true, colorScheme: scheme });
const page = await ctx.newPage();
await page.clock.setFixedTime(new Date('2026-10-08T10:00:00'));
const errores = [];
page.on('pageerror', e => errores.push(String(e)));
page.on('console', m => { if (m.type() === 'error' && !/fonts\.g/.test(m.text())) errores.push(m.text()); });
const shot = async n => { await page.waitForFunction(() => !document.querySelector('#toast.on'), null, { timeout: 5000 }).catch(() => {}); return page.screenshot({ path: join(OUT, `${scheme}-${n}.png`), fullPage: false }); };
const check = (cond, msg) => { if (!cond) throw new Error('FALLA: ' + msg); console.log('OK  ' + msg); };

await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForSelector('#bv-n');
await shot('00-bienvenida');
await page.fill('#bv-n', 'Carmen');
await page.click('#bv-ok');
await page.waitForSelector('text=Aún no hay plazos');
check(await page.isVisible('text=Carmen'), 'saluda por el nombre');
await shot('01-inicio-vacio');

// Nueva notificación con PDF
await page.click('.fab');
await page.waitForSelector('#pdfIn', { state: 'attached' });
await page.setInputFiles('#pdfIn', pdf);
await page.waitForSelector('text=He encontrado', { timeout: 30000 });
const v = async f => page.inputValue(`[data-f="${f}"]`);
check((await v('organo')).includes('Juzgado de Primera Instancia') && (await v('organo')).includes('Sevilla'), 'lee el juzgado: ' + await v('organo'));
check((await v('procedimiento')).includes('123/2026'), 'lee el procedimiento: ' + await v('procedimiento'));
check((await v('cliente')).includes('contra'), 'lee las partes: ' + await v('cliente'));
check(await v('cantidad') === '5', 'lee el plazo de cinco días');
check(await v('recepcion') === '2026-10-05', 'lee la fecha de envío de la carátula');
check((await v('actuacion')).toLowerCase().includes('alega'), 'propone la actuación: ' + await v('actuacion'));
check(await page.isVisible('.result >> text=Miércoles, 14 de octubre de 2026'), 'calcula el vencimiento (14 oct, con el puente del 12)');
await shot('02-nueva-leida');
await page.evaluate(() => document.querySelector('#calc').scrollIntoView());
await shot('03-nueva-calculo');

// Cambiar a "después de las 15:00" mueve el cálculo un día
await page.click('[data-act="hora"][data-v="despues"]');
check(await page.isVisible('.result >> text=Jueves, 15 de octubre de 2026'), 'después de las 15:00 vence un día más tarde');
await page.click('[data-act="hora"][data-v="antes"]');

// Abogado nuevo desde el formulario
await page.click('[data-act="nuevoAbogado"]');
await page.fill('#ab-n', 'Ana López'); await page.fill('#ab-e', 'ana@despacho.es'); await page.fill('#ab-t', '600111222');
await page.click('#ab-ok');
await page.waitForFunction(() => document.querySelector('[data-f="abogadoId"]').selectedOptions[0].textContent === 'Ana López');
check(true, 'el abogado nuevo queda elegido');
await page.click('[data-act="guardar"]');
await page.waitForSelector('.d-title');
check(await page.isVisible('text=Vence el miércoles, 14 de octubre de 2026'), 'ficha del plazo con el vencimiento');
check(await page.isVisible('text=Quedan 3 días hábiles'), 'cuenta los días hábiles que quedan (9, 13 y 14)');
await shot('04-ficha');

// Avisar al abogado
await page.click('[data-act="avisar"]');
const aviso = await page.inputValue('#av-t');
check(aviso.includes('Hola Ana') && aviso.includes('Vence: miércoles, 14 de octubre de 2026') && aviso.includes('15:00 del jueves, 15 de octubre'), 'texto del aviso al abogado');
await shot('05-avisar');
await page.click('.sclose');

// Calendario .ics
const [dl] = await Promise.all([page.waitForEvent('download'), page.click('[data-act="ics"]')]);
const ics = readFileSync(await dl.path(), 'utf8');
check(ics.includes('DTSTART;VALUE=DATE:20261014') && ics.includes('BEGIN:VALARM'), 'archivo de calendario con aviso');

// Un segundo plazo a mano, que vence hoy, y uno con tiempo
for (const [rec, act, n] of [['2026-09-29', 'Recurso de reposición', 6], ['2026-10-07', 'Contestar demanda (ordinario)', 20]]) {
  await page.goto(`http://127.0.0.1:${port}/`); await page.waitForSelector('.fab');
  await page.click('.fab'); await page.waitForSelector('[data-f="recepcion"]');
  await page.fill('[data-f="recepcion"]', rec); await page.fill('[data-f="actuacion"]', act); await page.fill('[data-f="cantidad"]', String(n));
  await page.fill('[data-f="organo"]', 'Juzgado de lo Mercantil nº 1'); await page.fill('[data-f="procedimiento"]', 'Concurso 45/2026');
  await page.click('[data-act="guardar"]'); await page.waitForSelector('.d-title');
}
await page.click('[data-act="back"]');
await page.waitForSelector('.pcard');
check(await page.locator('.pcard').count() === 3, 'tres plazos en la lista');
check(await page.isVisible('.badge.b-hoy'), 'uno vence hoy (en rojo)');
check(await page.isVisible('.badge.b-pronto') && await page.isVisible('.badge.b-tiempo'), 'otro próximo (ámbar) y otro con tiempo (verde)');
await shot('06-inicio');
await page.screenshot({ path: join(OUT, `${scheme}-06b-inicio-completo.png`), fullPage: true });

// Filtro y búsqueda
await page.click('[data-act="filtro"][data-k="hoy"]');
check(await page.locator('.pcard').count() === 1, 'el filtro «Hoy» deja solo el urgente');
await page.click('[data-act="filtro"][data-k="hoy"]');
await page.fill('#q', 'sevilla');
check(await page.locator('.pcard').count() === 1, 'la búsqueda encuentra por juzgado');
await page.fill('#q', '');

// Calendario
await page.click('[data-go="calendario"]');
await page.waitForSelector('.grid');
await page.click('.day[data-d="2026-10-14"]');
check(await page.isVisible('.dcard >> text=Alegaciones'), 'el calendario enseña lo que vence el 14');
await page.click('.day[data-d="2026-10-12"]');
check(await page.isVisible('text=Fiesta Nacional de España'), 'el 12 de octubre sale como inhábil');
await page.click('.day[data-d="2026-10-14"]');
await shot('07-calendario');

// Menú, festivos y ayuda
await page.click('[data-act="menu"]'); await page.waitForSelector('.drawer');
await shot('08-menu');
await page.click('.drawer [data-go="festivos"]'); await page.waitForSelector('text=Tus festivos');
await page.click('[data-act="quickFest"]');
await page.waitForSelector('.fest >> text=Jueves Santo', { timeout: 5000 });
check(true, 'añade Jueves Santo con un toque');
await shot('09-festivos');
await page.goto(`http://127.0.0.1:${port}/`); await page.waitForSelector('.pcard');
await page.click('[data-go="ayuda"]'); await page.waitForSelector('text=Paso a paso');
await shot('10-ayuda');

// Marcar como hecho y comprobar que se guarda tras recargar
await page.goto(`http://127.0.0.1:${port}/`); await page.waitForSelector('.pcard');
await page.click('.pcard:has(.b-hoy)'); await page.waitForSelector('[data-act="hecho"]');
await page.click('[data-act="hecho"]');
await page.waitForSelector('.count.c-hecho', { timeout: 5000 });
check(true, 'se marca como hecho');
await page.reload(); await page.waitForSelector('.d-title, .pcard');
await page.goto(`http://127.0.0.1:${port}/`); await page.waitForSelector('.pcard');
check(await page.locator('.pcard').count() === 2 && await page.isVisible('text=Ver los hechos (1)'), 'tras recargar sigue todo (2 pendientes y 1 hecho)');

// Copia de seguridad
await page.click('[data-act="menu"]'); await page.click('.drawer [data-go="copia"]');
const [dl2] = await Promise.all([page.waitForEvent('download'), page.click('[data-act="exportar"]')]);
const copia = JSON.parse(readFileSync(await dl2.path(), 'utf8'));
check(copia.plazos.length === 3 && Object.keys(copia.pdfs).length === 1 && copia.abogados.length === 1, 'la copia lleva plazos, PDF y abogados');

// Sin conexión: con el service worker activo se apaga la red y se recarga
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForFunction(() => navigator.serviceWorker && navigator.serviceWorker.controller, null, { timeout: 20000 });
await page.waitForTimeout(1500);
await ctx.setOffline(true); srv.close();
await page.reload(); await page.waitForSelector('.pcard', { timeout: 20000 });
check(await page.locator('.pcard').count() === 2, 'sin cobertura arranca y enseña los plazos');
await browser.close();
const reales = errores.filter(e => !/ERR_INTERNET_DISCONNECTED|Failed to load resource|net::/.test(e));
if (reales.length) { console.error('Errores en la página:\n' + reales.join('\n')); process.exit(1); }
console.log('E2E OK');
