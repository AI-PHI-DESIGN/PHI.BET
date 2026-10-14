// Comprueba el cálculo de plazos con casos conocidos (fines de semana, puente, 15:00, agosto, Navidad, meses).
// Uso: node tools/test-plazos.mjs
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { serve, CHROME } from './serve.mjs';
const { srv, port } = await serve(process.cwd());
const browser = await chromium.launch({ executablePath: CHROME });
const page = await browser.newPage();
page.on('pageerror', e => { console.error('PAGE ERROR', e); process.exitCode = 1; });
await page.goto(`http://127.0.0.1:${port}/`);
await page.waitForFunction(() => typeof calcular === 'function');
const casos = [
  // [descripción, entrada, vence esperado, notificada esperada, gracia esperada]
  ['Lunes por la mañana, 5 días, con el puente del 12 de octubre', { recepcion: '2026-10-05', hora: 'antes', cantidad: 5, unidad: 'dias' }, '2026-10-14', '2026-10-06', '2026-10-15'],
  ['Viernes después de las 15:00, 5 días', { recepcion: '2026-10-16', hora: 'despues', cantidad: 5, unidad: 'dias' }, '2026-10-27', '2026-10-20', '2026-10-28'],
  ['Viernes antes de las 15:00, 5 días', { recepcion: '2026-10-16', hora: 'antes', cantidad: 5, unidad: 'dias' }, '2026-10-26', '2026-10-19', '2026-10-27'],
  ['Sábado (inhábil), 5 días', { recepcion: '2026-10-17', hora: 'antes', cantidad: 5, unidad: 'dias' }, '2026-10-27', '2026-10-20', '2026-10-28'],
  ['Final de julio, 20 días: agosto no cuenta', { recepcion: '2026-07-30', hora: 'antes', cantidad: 20, unidad: 'dias' }, '2026-09-28', '2026-07-31', '2026-09-29'],
  ['Final de julio, 20 días, urgente: agosto cuenta (15 ago festivo)', { recepcion: '2026-07-30', hora: 'antes', cantidad: 20, unidad: 'dias', urgente: true }, '2026-08-28', '2026-07-31', '2026-08-31'],
  ['22 de diciembre, 5 días: del 24 al 6 de enero no cuentan', { recepcion: '2026-12-22', hora: 'antes', cantidad: 5, unidad: 'dias' }, '2027-01-13', '2026-12-23', '2027-01-14'],
  ['Un mes, termina en sábado y pasa al lunes', { recepcion: '2026-03-10', hora: 'antes', cantidad: 1, unidad: 'meses' }, '2026-04-13', '2026-03-11', '2026-04-14'],
  ['Semana Santa: Viernes Santo 3 abril 2026 no cuenta', { recepcion: '2026-03-30', hora: 'antes', cantidad: 5, unidad: 'dias' }, '2026-04-08', '2026-03-31', '2026-04-09'],
];
let fallos = 0;
for (const [desc, p, vence, notif, gracia] of casos) {
  const c = await page.evaluate(p => calcular(p), p);
  const ok = c.vence === vence && c.notificada === notif && c.gracia === gracia;
  if (!ok) fallos++;
  console.log(`${ok ? 'OK ' : 'MAL'} ${desc}: notificada ${c.notificada}, vence ${c.vence}, gracia ${c.gracia}${ok ? '' : `  (esperado ${notif} / ${vence} / ${gracia})`}`);
}
// Festivo local añadido por la usuaria: el 14 de octubre deja de contar
const conLocal = await page.evaluate(() => { S.festivos = [{ fecha: '2026-10-14', nombre: 'Fiesta local' }]; const c = calcular({ recepcion: '2026-10-05', hora: 'antes', cantidad: 5, unidad: 'dias' }); S.festivos = []; return c.vence; });
console.log(`${conLocal === '2026-10-15' ? 'OK ' : 'MAL'} Festivo local el 14 de octubre: vence ${conLocal}`); if (conLocal !== '2026-10-15') fallos++;
const pas = await page.evaluate(() => [pascua(2024), pascua(2025), pascua(2026), pascua(2027)]);
const pasOk = pas.join() === '2024-03-31,2025-04-20,2026-04-05,2027-03-28';
console.log(`${pasOk ? 'OK ' : 'MAL'} Domingo de Pascua 2024-2027: ${pas.join(', ')}`); if (!pasOk) fallos++;
await browser.close(); srv.close();
if (fallos) { console.error(fallos + ' casos fallan'); process.exit(1); }
console.log('Todos los casos correctos');
