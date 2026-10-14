// Crea PDF de ejemplo con el aspecto de notificaciones y escritos reales (texto real, Helvetica WinAnsi)
// para probar la lectura automática.
import { writeFileSync } from 'node:fs';
// Modelos (datos inventados): lexnet (carátula + diligencia), gva-subsanar, gva-auto (penal, sin plazo propio), escrito.
// Uso: node tools/make-test-pdf.mjs salida.pdf [modelo]
const MODELOS = {
  'gva-subsanar': ['TRIBUNAL DE INSTANCIA DE PICASSENT', 'Órgano judicial: Sección Civil y de Instrucción del Tribunal de', 'Instancia de Picassent. Plaza nº 2', 'N.I.G: 4619441120260009999',
    'Tipo y número de procedimiento: Juicio verbal (250.2) 321/2026', 'Demandante D./Dª.Talleres Ejemplo S.L.', 'Abogado/a: D.PEDRO PRUEBA', 'Demandado D./Dª.Muebles Ficticios S.A.',
    'DILIGENCIA DE ORDENACIÓN', 'En Picassent, a veintidós de septiembre de dos mil veintiséis.', 'Observándose la omisión en la constitución del depósito necesario para recurrir,',
    'se concede a dicha parte un plazo de dos días para subsanar el defecto advertido.', 'MODO DE IMPUGNACIÓN: recurso de REPOSICIÓN ante la Letrada de la Administración de Justicia,',
    'en el plazo de cinco días hábiles, contados desde el día siguiente de la notificación.', 'Este documento incorpora firma electrónica de acuerdo a la Ley 6/2020.'],
  'gva-auto': ['TRIBUNAL DE INSTANCIA DE VALÈNCIA', 'Órgano judicial: Sección de lo Penal del Tribunal de Instancia de Valencia.', 'Plaza nº 20', 'N.I.G: 4625043220240099999',
    'Tipo y número de procedimiento: Procedimiento abreviado 999/2026', 'Denunciante D.LUIS EJEMPLO GARCIA', 'Denunciado Dª.ANA PRUEBA LOPEZ y MARTA FICTICIA RUIZ', 'A U T O',
    'SE ACUERDA: DEJAR SIN EFECTO LA BÚSQUEDA, DETENCIÓN Y PRESENTACIÓN.', 'MODO DE IMPUGNACIÓN : mediante interposición de RECURSO DE', 'REFORMA y subsidiario de APELACION dentro de los TRES DIAS',
    'siguientes a su notificación o RECURSO DE APELACIÓN directo', 'dentro de los CINCO DIAS siguientes a su notificación.'],
  'escrito': ['Juicio Verbal (250.1.14) n º 111/2025.', 'A LA SECCIÓN CIVIL Y DE INSTRUCCIÓN DEL TRIBUNAL DE', 'INSTANCIA DE QUART DE POBLET. PLAZA Nº2',
    'MARIA PROCURADORA EJEMPLO, Procuradora de los Tribunales, en nombre y', 'representación de Dª. LUCIA CLIENTE FICTICIA, según consta en los autos,',
    'ante el Tribunal comparezco y como mejor proceda en Derecho, DIGO:', 'Que se nos indica que en el plazo de cinco días deben indicar las personas a citar.', 'SUPLICO AL TRIBUNAL que tenga por presentado este escrito.']
};
const modelo = process.argv[3] || 'lexnet';
const lineas = MODELOS[modelo] ? MODELOS[modelo].map(l => [l, 10]) : [
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
