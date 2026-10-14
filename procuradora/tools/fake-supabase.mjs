// Imitación mínima de Supabase (Auth + tabla registros + Storage) para probar la sincronización sin internet.
// Solo implementa lo que usa la app, con las mismas rutas, cabeceras y formatos de error. Datos en memoria.
import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';
export async function fakeSupabase({ confirmar = false } = {}) {
  const users = new Map(), tokens = new Map(), refresh = new Map(), filas = new Map(), objetos = new Map();
  let reloj = Date.now();
  const sesion = u => { const at = 'at-' + randomUUID(), rt = 'rt-' + randomUUID(); tokens.set(at, u.id); refresh.set(rt, u.id); return { access_token: at, refresh_token: rt, token_type: 'bearer', expires_in: 3600, user: { id: u.id, email: u.email } }; };
  const leer = req => new Promise(r => { const b = []; req.on('data', c => b.push(c)); req.on('end', () => r(Buffer.concat(b))); });
  const srv = createServer(async (req, res) => {
    const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,DELETE,OPTIONS' };
    const json = (st, o) => { res.writeHead(st, { ...cors, 'content-type': 'application/json' }); res.end(o === undefined ? '' : JSON.stringify(o)); };
    if (req.method === 'OPTIONS') { res.writeHead(204, cors); return res.end(); }
    const url = new URL(req.url, 'http://x'), p = url.pathname, body = await leer(req);
    const js = () => { try { return JSON.parse(body.toString() || '{}'); } catch { return {}; } };
    if (!req.headers.apikey) return json(401, { message: 'No API key found in request' });
    const uid = tokens.get((req.headers.authorization || '').replace(/^Bearer /, ''));
    srv.stats.peticiones++;
    if (p === '/auth/v1/signup' && req.method === 'POST') {
      const { email, password } = js();
      if (!password || password.length < 6) return json(422, { code: 'weak_password', msg: 'Password should be at least 6 characters.' });
      if ([...users.values()].some(u => u.email === email)) return json(422, { code: 'user_already_exists', msg: 'User already registered' });
      const u = { id: randomUUID(), email, password, confirmado: !confirmar }; users.set(u.id, u);
      return json(200, confirmar ? { id: u.id, email } : sesion(u));
    }
    if (p === '/auth/v1/token' && req.method === 'POST') {
      const b = js(), g = url.searchParams.get('grant_type');
      if (g === 'password') {
        const u = [...users.values()].find(u => u.email === b.email && u.password === b.password);
        if (!u) return json(400, { error: 'invalid_grant', error_description: 'Invalid login credentials' });
        if (!u.confirmado) return json(400, { error: 'invalid_grant', error_description: 'Email not confirmed' });
        return json(200, sesion(u));
      }
      if (g === 'refresh_token') { const id = refresh.get(b.refresh_token); if (!id) return json(400, { error_description: 'Invalid Refresh Token' }); refresh.delete(b.refresh_token); return json(200, sesion(users.get(id))); }
    }
    if (p === '/auth/v1/recover' && req.method === 'POST') { srv.stats.recover.push(js().email); return json(200, {}); }
    if (p === '/auth/v1/logout') { tokens.delete((req.headers.authorization || '').replace(/^Bearer /, '')); res.writeHead(204, cors); return res.end(); }
    if (!uid) return json(401, { code: 401, message: 'JWT expired' });
    if (p === '/auth/v1/user') {
      const u = users.get(uid);
      if (req.method === 'PUT') { const b = js(); if (b.password) u.password = b.password; }
      return json(200, { id: u.id, email: u.email });
    }
    if (p === '/rest/v1/registros' && req.method === 'POST') {
      for (const f of JSON.parse(body.toString())) { reloj = Math.max(reloj + 1, Date.now()); filas.set(`${uid}|${f.tipo}|${f.id}`, { user_id: uid, tipo: f.tipo, id: f.id, datos: f.datos, borrado: !!f.borrado, updated_at: new Date(reloj).toISOString().replace('Z', '123+00:00') }); }
      res.writeHead(201, cors); return res.end();
    }
    if (p === '/rest/v1/registros' && req.method === 'GET') {
      const gt = (url.searchParams.get('updated_at') || 'gt.1970-01-01T00:00:00Z').slice(3), lim = +url.searchParams.get('limit') || 1000, off = +url.searchParams.get('offset') || 0;
      const ms = s => Date.parse(s.replace(/(\.\d{3})\d+/, '$1'));
      const r = [...filas.values()].filter(f => f.user_id === uid && ms(f.updated_at) > ms(gt)).sort((a, b) => ms(a.updated_at) - ms(b.updated_at));
      return json(200, r.slice(off, off + lim).map(({ user_id, ...f }) => f));
    }
    if (p === '/functions/v1/redactar' && req.method === 'POST') {
      const b = js(); srv.stats.ia.push(b);
      if (!b.peticion) return json(400, { error: 'Escribe qué quieres decir en el correo.' });
      const vence = (b.contexto.match(/Vence: (.+)/) || [])[1] || '';
      return json(200, { asunto: 'Traslado de notificación', cuerpo: `Hola:\n\nTe traslado la notificación. ${b.peticion}.${vence ? ' Vence el ' + vence + '.' : ''}\n\nUn saludo.` });
    }
    const m = p.match(/^\/storage\/v1\/object\/(?:authenticated\/)?pdfs\/(.+)$/);
    if (m) {
      if (m[1].split('/')[0] !== uid) return json(403, { statusCode: '403', error: 'Unauthorized', message: 'new row violates row-level security policy' });
      if (req.method === 'POST' || req.method === 'PUT') { objetos.set(m[1], body); return json(200, { Key: 'pdfs/' + m[1] }); }
      if (req.method === 'DELETE') { objetos.delete(m[1]); return json(200, {}); }
      if (!objetos.has(m[1])) return json(400, { statusCode: '404', error: 'not_found', message: 'Object not found' });
      res.writeHead(200, { ...cors, 'content-type': 'application/pdf' }); return res.end(objetos.get(m[1]));
    }
    json(404, { message: 'ruta no imitada: ' + req.method + ' ' + p });
  });
  srv.stats = { peticiones: 0, recover: [], ia: [] };
  srv.datos = { users, filas, objetos };
  await new Promise(r => srv.listen(0, r));
  return { srv, url: `http://127.0.0.1:${srv.address().port}` };
}
