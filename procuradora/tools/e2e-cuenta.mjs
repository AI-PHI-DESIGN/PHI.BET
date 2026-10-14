// Prueba de cuentas y sincronización con dos "dispositivos" (dos navegadores separados) contra fake-supabase.
// Uso: node tools/e2e-cuenta.mjs [dirCapturas]
import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { serve, CHROME } from './serve.mjs';
import { fakeSupabase } from './fake-supabase.mjs';
const OUT = process.argv[2] || 'shots'; mkdirSync(OUT, { recursive: true });
const pdf = join(OUT, 'notificacion-prueba.pdf'); execFileSync('node', ['tools/make-test-pdf.mjs', pdf]);
const sb = await fakeSupabase();
const { srv, port } = await serve(process.cwd(), (p, body) => p === '/index.html' ? Buffer.from(body.toString('utf8').replace("const NUBE = { url: '', key: '' };", `const NUBE = { url: '${sb.url}', key: 'anon-de-prueba' };`)) : body);
const APP = `http://127.0.0.1:${port}/`;
const browser = await chromium.launch({ executablePath: CHROME });
const errores = [];
const dispositivo = async nombre => {
  const ctx = await browser.newContext({ viewport: { width: 412, height: 915 }, deviceScaleFactor: 2, locale: 'es-ES', isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  page.on('pageerror', e => errores.push(nombre + ': ' + e));
  return { ctx, page };
};
const check = (c, m) => { if (!c) throw new Error('FALLA: ' + m); console.log('OK  ' + m); };
const espera = (page, sel, t = 10000) => page.waitForSelector(sel, { timeout: t });
const shot = async (page, n) => { await page.waitForFunction(() => !document.querySelector('#toast.on'), null, { timeout: 5000 }).catch(() => {}); await page.screenshot({ path: join(OUT, `cuenta-${n}.png`) }); };
const sincronizado = page => page.waitForFunction(() => N.estado === 'ok' && !N.curso && !Object.keys(N.pend).length, null, { timeout: 15000 });

// --- Móvil: crea la cuenta ---
const A = await dispositivo('móvil');
await A.page.goto(APP);
await espera(A.page, '#lg-form');
check(await A.page.isVisible('text=Tu agenda de plazos, en todos tus dispositivos'), 'sin cuenta, la app pide entrar');
await shot(A.page, '01-entrar');
await A.page.click('[data-act="lgModo"][data-v="crear"]');
await A.page.fill('#lg-e', 'carmen@ejemplo.com'); await A.page.fill('#lg-p', '123');
await A.page.click('#lg-ok');
await espera(A.page, '#lg-msg .err');
check((await A.page.textContent('#lg-msg')).includes('al menos 6'), 'avisa si la contraseña es corta');
await A.page.fill('#lg-p', 'secreta123');
await shot(A.page, '02-crear');
await A.page.click('#lg-ok');
await espera(A.page, '#bv-n');
check(true, 'cuenta creada; aparece la bienvenida');
await A.page.fill('#bv-n', 'Carmen'); await A.page.click('#bv-ok');
await espera(A.page, 'text=Aún no hay plazos');

// Crea un plazo con PDF, un abogado y un festivo
await A.page.click('.fab'); await A.page.setInputFiles('#pdfIn', pdf);
await espera(A.page, 'text=He encontrado', 30000);
await A.page.click('[data-act="nuevoAbogado"]'); await A.page.fill('#ab-n', 'Ana López'); await A.page.fill('#ab-e', 'ana@despacho.es'); await A.page.click('#ab-ok');
await A.page.waitForFunction(() => document.querySelector('[data-f="abogadoId"]').selectedOptions[0].textContent === 'Ana López');
await A.page.click('[data-act="guardar"]'); await espera(A.page, '.d-title');
await A.page.goto(APP + '#'); await espera(A.page, '.pcard');
await A.page.evaluate(() => { S.festivos.push({ fecha: '2026-11-20', nombre: 'Fiesta local' }); return saveKV('festivos'); });
await sincronizado(A.page);
check(await A.page.isVisible('#sync >> text=Guardado en tu cuenta'), 'el móvil enseña «Guardado en tu cuenta»');
await A.page.waitForFunction(() => Object.keys(N.pdfOk).length === 1, null, { timeout: 10000 });
check(sb.srv.datos.objetos.size === 1, 'el PDF se ha subido a la cuenta');
await shot(A.page, '03-inicio-con-cuenta');

// --- Redactar con IA desde la ficha del plazo ---
await A.page.click('.pcard'); await espera(A.page, '[data-act="iaPlazo"]');
await A.page.click('[data-act="iaPlazo"]'); await espera(A.page, '#ia-pet');
check((await A.page.inputValue('#ia-pet')).includes('traslado') && await A.page.inputValue('#ia-para') !== '', 'la IA se abre con el asunto, el abogado y una idea ya puestos');
await A.page.click('[data-act="iaTono"][data-v="formal"]');
await A.page.click('[data-act="iaRedactar"]'); await espera(A.page, '#ia-cu');
const enviado = sb.srv.stats.ia.at(-1);
check(enviado.tono === 'formal' && enviado.contexto.includes('Vence: jueves, 15 de octubre de 2026') && enviado.contexto.includes('Destinatario: Ana López'), 'a la IA le llegan los datos y la fecha calculada por la app');
check(enviado.resolucion.includes('cinco días'), 'y el texto del PDF de la notificación');
check((await A.page.inputValue('#ia-cu')).includes('Vence el jueves'), 'el correo redactado aparece para revisarlo');
await shot(A.page, '07-ia');
await A.page.evaluate(() => document.querySelector('.hero').scrollIntoView());
await shot(A.page, '07b-ia-arriba');
await A.page.goto(APP + '#'); await espera(A.page, '.pcard');

// --- Ordenador: entra con la misma cuenta y lo ve todo ---
const B = await dispositivo('ordenador');
await B.page.goto(APP); await espera(B.page, '#lg-form');
await B.page.fill('#lg-e', 'carmen@ejemplo.com'); await B.page.fill('#lg-p', 'mal');
await B.page.click('#lg-ok'); await espera(B.page, '#lg-msg .err');
check((await B.page.textContent('#lg-msg')).includes('al menos 6') , 'valida la contraseña antes de enviar');
await B.page.fill('#lg-p', 'equivocada'); await B.page.click('#lg-ok');
await B.page.waitForFunction(() => document.querySelector('#lg-msg').textContent.includes('no son correctos'));
check(true, 'contraseña equivocada: «El correo o la contraseña no son correctos»');
await B.page.fill('#lg-p', 'secreta123'); await B.page.click('#lg-ok');
await espera(B.page, '.pcard');
check(!(await B.page.isVisible('#bv-n')), 'en el segundo dispositivo no vuelve a pedir el nombre');
check(await B.page.isVisible('text=Carmen') && await B.page.isVisible('.pcard >> text=Alegaciones'), 'el ordenador ve el plazo y el nombre');
check(await B.page.evaluate(() => S.abogados.length === 1 && S.festivos.some(f => f.fecha === '2026-11-20')), 'llegan abogados y festivos');
await B.page.click('.pcard'); await espera(B.page, '[data-act="verPdf"]');
const pdfB = await B.page.evaluate(async () => { const x = await obtenerPDF(findPlazo(S.view.id)); return x ? x.blob.size : 0; });
check(pdfB > 500, 'el PDF se descarga de la cuenta en el ordenador');
await B.page.click('[data-act="hecho"]'); await espera(B.page, '.count.c-hecho');
await sincronizado(B.page);

// --- Móvil: recibe el cambio ---
await A.page.evaluate(() => sincronizar());
await A.page.waitForFunction(() => S.plazos[0] && S.plazos[0].hecho === true, null, { timeout: 10000 });
check(true, 'el «hecho» del ordenador llega al móvil');

// --- Sin conexión en el móvil: el cambio espera y se sube al volver ---
await A.ctx.setOffline(true);
await A.page.evaluate(() => { const p = S.plazos[0]; p.notas = 'Cambio hecho sin cobertura'; return savePlazo(p); });
await A.page.waitForFunction(() => N.estado === 'offline', null, { timeout: 10000 });
await A.page.goto(APP + '#').catch(() => {});
check(true, 'sin cobertura avisa «se guardará al volver»');
await shot(A.page, '04-sin-conexion');
await A.ctx.setOffline(false);
await A.page.evaluate(() => sincronizar());
await sincronizado(A.page);
await B.page.evaluate(() => sincronizar());
await B.page.waitForFunction(() => S.plazos[0] && S.plazos[0].notas === 'Cambio hecho sin cobertura', null, { timeout: 10000 });
check(true, 'el cambio hecho sin cobertura llega al ordenador al volver la conexión');

// --- Borrar en un sitio borra en el otro ---
await B.page.evaluate(async () => { const id = S.plazos[0].id; await Store.del(id); S.plazos = []; marcar('plazo:' + id); });
await sincronizado(B.page);
await A.page.evaluate(() => sincronizar());
await A.page.waitForFunction(() => S.plazos.length === 0, null, { timeout: 10000 });
check(sb.srv.datos.objetos.size === 0, 'borrar un plazo lo quita del otro dispositivo y su PDF de la cuenta');

// --- Contraseña olvidada y menú de cuenta ---
await A.page.click('[data-act="menu"]'); await espera(A.page, '.drawer');
check(await A.page.isVisible('.drawer >> text=carmen@ejemplo.com'), 'el menú enseña la cuenta');
await shot(A.page, '05-menu');
await A.page.click('.drawer [data-act="salir"]');
await espera(A.page, '#cf-si'); await A.page.click('#cf-si');
await espera(A.page, '#lg-form');
check(await A.page.evaluate(async () => (await Store.all()).length === 0 && S.abogados.length === 0), 'cerrar sesión borra los datos del dispositivo');
await A.page.click('[data-act="olvido"]'); await A.page.fill('#ol-e', 'carmen@ejemplo.com'); await A.page.click('#ol-ok');
await espera(A.page, '#ol-msg .found');
check(sb.srv.stats.recover.includes('carmen@ejemplo.com'), 'pide el correo para cambiar la contraseña');
await shot(A.page, '06-olvido');

// --- Volver a entrar recupera todo (abogado, festivo y nombre) ---
await A.page.click('.sclose');
await A.page.fill('#lg-e', 'carmen@ejemplo.com'); await A.page.fill('#lg-p', 'secreta123'); await A.page.click('#lg-ok');
await espera(A.page, 'text=Carmen');
await A.page.waitForFunction(() => S.abogados.length === 1, null, { timeout: 10000 });
check(true, 'al volver a entrar se recupera todo de la cuenta');

// --- Enlace del correo de cambiar contraseña ---
const C = await dispositivo('tablet');
const tok = await A.page.evaluate(() => N.ses);
await C.page.goto(APP + `#access_token=${tok.access_token}&refresh_token=${tok.refresh_token}&expires_in=3600&type=recovery`);
await espera(C.page, '#cl-p');
await C.page.fill('#cl-p', 'nuevaClave9'); await C.page.click('[data-act="guardarClave"]');
await espera(C.page, '.glass');
check([...sb.srv.datos.users.values()][0].password === 'nuevaClave9', 'el enlace del correo deja poner una contraseña nueva');

await browser.close(); srv.close(); sb.srv.close();
if (errores.length) { console.error(errores.join('\n')); process.exit(1); }
console.log('CUENTA OK');
