// Crea un PDF de ejemplo con el aspecto de una notificación de LexNET (texto real, Helvetica WinAnsi)
// para probar la lectura automática. Uso: node tools/make-test-pdf.mjs salida.pdf
import { writeFileSync } from 'node:fs';
const lineas = [
  ['Fecha-hora envío: 05/10/2026 10:23', 9],
  ['JUZGADO DE PRIMERA INSTANCIA Nº 3 DE SEVILLA', 13],
  ['NIG: 4109142120260012345', 10],
  ['Procedimiento: Procedimiento Ordinario 123/2026', 10],
  ['DEMANDANTE: D/ña. MARIA GARCIA LOPEZ', 10],
  ['DEMANDADO: BANCO EJEMPLO S.A.', 10],
  ['DILIGENCIA DE ORDENACIÓN', 13],
  ['Con el anterior escrito, únase a los autos y dese traslado a la parte demandante', 10],
  ['para que en el plazo de cinco días formule las alegaciones que estime oportunas.', 10],
];
let y = 780, ops = 'BT\n';
for (const [t, sz] of lineas) { const s = t.replace(/[\\()]/g, m => '\\' + m); ops += `/F1 ${sz} Tf 1 0 0 1 56 ${y} Tm (${s}) Tj\n`; y -= sz + 12; }
ops += 'ET\n';
const content = Buffer.from(ops, 'latin1');
const objs = [
  '<< /Type /Catalog /Pages 2 0 R >>',
  '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
  '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
  null,
  '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
];
const parts = [Buffer.from('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n', 'latin1')]; const offs = [];
let len = parts[0].length;
objs.forEach((o, i) => {
  offs.push(len);
  const b = o === null ? Buffer.concat([Buffer.from(`${i + 1} 0 obj\n<< /Length ${content.length} >>\nstream\n`), content, Buffer.from('endstream\nendobj\n')]) : Buffer.from(`${i + 1} 0 obj\n${o}\nendobj\n`, 'latin1');
  parts.push(b); len += b.length;
});
const xref = `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n` + offs.map(o => String(o).padStart(10, '0') + ' 00000 n \n').join('') + `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${len}\n%%EOF\n`;
parts.push(Buffer.from(xref));
writeFileSync(process.argv[2] || 'notificacion-prueba.pdf', Buffer.concat(parts));
console.log('pdf ok');
