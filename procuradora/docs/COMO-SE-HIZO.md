# Cómo se hizo «Mis Plazos» (receta para repetirlo igual)

Recoge las decisiones y los pasos seguidos, para que una petición futura del tipo «hazme una app para una
procuradora» o «una agenda de plazos» se resuelva de la misma manera. Sigue la misma receta que «Visitas de Obra»
(repo `AI-PHI-DESIGN/AI-PHI-DESIGN`, `docs/COMO-SE-HIZO.md`), adaptada.

## 1. Petición original

- Para: la madre del usuario, **procuradora de los tribunales**, sin perfil técnico. Hay que pensar en ella al
  escribir cada texto de la pantalla: frases cortas, tuteo, nada de jerga informática.
- Se partió de una lluvia de ideas (resumir resoluciones, redactar correos y escritos, agenda de plazos,
  traslados, provisiones de fondos). Se eligió **la agenda de plazos** porque es lo que más estrés quita y donde
  un despiste sale más caro.
- Diseño pedido: «bonito y que mi madre lo entienda bien». Referencia visual: un *dribbble* de gestor de archivos
  en **neumorfismo lavanda + índigo** (parte oscura arriba con curva en S hacia la parte clara, baldosas blandas
  con iconos de color, botón central redondo en una muesca de la barra inferior, tira de días en «pastillas»
  verticales con el día elegido más alto y claro).

## 2. Reglas jurídicas del cálculo (comprobadas antes de programar)

| Regla | Fuente |
|---|---|
| Recibida en LexNET **antes de las 15:00** de un día hábil → **notificada el día hábil siguiente** | art. 151.2 LEC (circulares de colegios de procuradores) |
| Recibida **después de las 15:00** o en día inhábil → se tiene por recibida el día hábil siguiente (y notificada el otro) | art. 151.2 LEC |
| El plazo **empieza al día siguiente** de la notificación | art. 133.1 LEC |
| Plazos por días: **solo días hábiles** | art. 133.2 LEC |
| Inhábiles: sábados, domingos, **24 y 31 de diciembre**, festivos nacionales, autonómicos y locales | art. 182 LOPJ |
| Inhábiles salvo urgentes: **agosto** y **del 24 de diciembre al 6 de enero** (LO 14/2022) | art. 183 LOPJ |
| Plazos por meses: **de fecha a fecha**; si no existe el día, último del mes; si acaba en inhábil, siguiente hábil | art. 133.3 y 133.4 LEC |
| **Día de gracia**: hasta las 15:00 del día hábil siguiente al vencimiento | art. 135.5 LEC |

Ojo con la memoria: el periodo del 24 dic al 6 ene inhábil **no** es de la LO 1/2025, es de la LO 14/2022.
Se verificó con búsqueda web antes de programar. Repetir la verificación si pasa tiempo: las reglas cambian.

Decisiones de prudencia:
- **Por defecto «antes de las 15:00»**, que da el vencimiento más temprano.
- Interruptor **«Asunto urgente»** (agosto y Navidad cuentan). Si el cálculo normal se ha saltado agosto o
  Navidad, la tarjeta del resultado dice **cuándo vencería si fuera urgente**, para que nunca pille por sorpresa.
- Siempre se enseña **«¿Cómo lo he calculado?»**: recepción, notificación, tramos de días contados y saltados con
  su motivo, vencimiento y día de gracia. Es lo que da confianza a quien conoce las reglas.
- Festivos autonómicos y locales: **no se inventan**. Los añade ella (con atajos para Jueves Santo y Lunes de Pascua,
  calculados con el algoritmo de Pascua).

## 3. Arquitectura (la misma de Visitas de Obra)

| Decisión | Motivo |
|---|---|
| **Un solo `index.html`** con CSS y JS inline, sin frameworks ni build | Se publica tal cual en GitHub Pages o como Artifact. |
| **PWA** (`manifest.webmanifest` + `sw.js` + iconos) | Icono en la pantalla de inicio y funciona sin cobertura. |
| **IndexedDB** `mis-plazos` con stores `plazos`, `kv` (abogados, festivos, perfil) y `pdfs` (Blob del PDF por plazo) | Los PDF ocupan; localStorage no basta. Respaldo en localStorage si no hay IndexedDB. |
| **pdf.js 4.10.38 (legacy build) copiado en `vendor/`** desde npm (`npm pack pdfjs-dist@4.10.38`), con los bytes de control escritos como `\xNN` (la publicación como Artifact rechaza archivos con bytes ESC; dentro de cadenas JS es equivalente) | Los CDN estaban bloqueados en el entorno y además así funciona sin cobertura. Se carga con `import()` solo al subir un PDF. El service worker lo precachea. |
| **Lectura del PDF con expresiones regulares** (`extraer()`), sin IA | Determinista, gratis y sin conexión. Lee juzgado, procedimiento, NIG, partes, tipo de resolución, «plazo de N días/meses» (con números en letra) y la fecha y hora de la carátula de LexNET. Si el PDF es una imagen escaneada, lo dice y se rellena a mano. |
| **Fechas como texto `AAAA-MM-DD` y aritmética en UTC** | Sin sorpresas por el cambio de hora. |
| **Aviso al abogado**: `mailto:` con asunto y cuerpo, `navigator.share` con el PDF como archivo, o copiar texto | El correo por `mailto:` no admite adjuntos; para mandar el PDF se usa Compartir. |
| **Calendario `.ics`** con dos `VALARM` (`-P1DT15H` y `-PT15H`: 9:00 dos días antes y el día anterior) | Recordatorios reales en el móvil sin servidor de notificaciones. |
| **Copia de seguridad** en JSON con los PDF en base64 | Los datos solo viven en el móvil. |
| `deliver()` en cascada: capacidad `downloads` de claude.ai → compartir (solo en móvil) → descarga | Igual que en Visitas de Obra. |

## 4. Diseño

- Tokens en `:root` con variante oscura (`prefers-color-scheme` y `data-theme`). Lavanda `#E4E5F4` / `#EBECF8`,
  índigo profundo `#3A3D86 → #24255A → #17183C`, acento `#5A5FE0`. Estados: rojo `#E8445F`, ámbar `#E8962A`,
  verde `#1FA878`.
- Sombras neumórficas: `--neu` (relieve), `--neu-sm`, `--neu-in` (hundido, para pulsado/seleccionado e inputs).
- **Curva en S** (`waveSVG()`): un `path` SVG con `preserveAspectRatio="none"` al pie de cada cabecera oscura,
  relleno del color de la parte clara. En el calendario se usa la inversa (`.wave-up`) para bajar de claro a oscuro.
- **Barra inferior con muesca**: rejilla `1fr 132px 1fr`; los lados son divs y el centro un SVG con la muesca, así
  la curva no se deforma con el ancho. El contenedor `#navwrap` es el `sticky` (no el `nav`, que no tendría sitio
  para pegarse).
- **Iconos de color** dibujados en SVG con degradados definidos una sola vez (`<defs>` oculto: `gPink`, `gOrange`,
  `gRed`, `gBlue`, `gGreen`, `gViolet`, `gTeal`).
- Pensado para ella: letra base 17 px, botones de 48–58 px, textos de ayuda bajo cada paso numerado, botón de
  **cerrar** visible en todas las hojas, saludo con su nombre, bienvenida la primera vez.
- Logotipo: calendario blanco con franja rosa-violeta y un check índigo. `tools/make-icons.mjs` rasteriza los PNG
  sin librerías.

## 5. Modelo de datos

```js
plazo = { id, recepcion: 'AAAA-MM-DD', hora: 'antes'|'despues', actuacion, cantidad, unidad: 'dias'|'meses',
          urgente, organo, procedimiento, nig, cliente, abogadoId, notas, resolucion, pdfName,
          hecho, hechoEn, trasladado: 'AAAA-MM-DD'|null, createdAt, updatedAt }
abogado = { id, nombre, email, telefono }
festivo = { fecha: 'AAAA-MM-DD', nombre }        // solo los que añade ella; los nacionales se calculan
perfil  = { nombre, firma, visto }
```

El vencimiento **no se guarda**: se calcula siempre con `calcular()`, así un festivo añadido después corrige
todos los plazos.

## 6. Pasos de construcción (en orden)

1. Comprobar las reglas jurídicas con búsqueda web (sección 2).
2. Crear la carpeta del proyecto y copiar pdf.js a `vendor/`.
3. Escribir `index.html`: tokens CSS, `<defs>` de degradados, utilidades de fecha, `inhabil()`, `calcular()`,
   `agrupar()` para el paso a paso, `estado()`, `Store`, vistas (`vHome`, `vNuevo`, `vPlazo`, `vCalendario`,
   `vAbogados`, `vFestivos`, `vPerfil`, `vAyuda`, `vCopia`), menú y hojas, `extraer()`, aviso, `.ics`, copia, `init`.
4. `sw.js` (red primero para la página con 4 s de espera, caché para el resto), `manifest.webmanifest` e iconos.
5. Pruebas:
   - `tools/test-plazos.mjs`: casos con fechas reales (puente del 12 de octubre, después de las 15:00, sábado,
     agosto, agosto urgente, Navidad, meses que acaban en sábado, Viernes Santo, festivo local) y Pascua 2024-2027.
   - `tools/make-test-pdf.mjs` genera un PDF con aspecto de notificación (Helvetica WinAnsi) y `tools/e2e.mjs`
     recorre todo con la fecha fijada (`page.clock.setFixedTime`) y saca capturas en claro y oscuro.
   - `tools/e2e-update.mjs`: versión nueva con la app instalada y arranque sin cobertura.
6. Revisar las capturas una por una y pulir (mayúsculas de las fechas, barra fija, bordes cortados…).
7. Commit, push y GitHub Pages.

## 7. Errores encontrados y cómo se evitaron

- **Recarga en la primera visita**: al activarse el service worker por primera vez salta `controllerchange`, y la
  app se recargaba (perdía lo que se estuviera escribiendo en la bienvenida). Solo se recarga si **ya había** una
  versión controlando la página al abrirla, y nunca con un formulario o una hoja abiertos.
- `text-transform: capitalize` en fechas largas pone «De Octubre De»: se usa `may()` para la primera letra.
- `position: sticky` en un elemento cuyo padre mide lo mismo que él no se pega: el sticky va en el contenedor.
- Las siglas en mayúsculas («S.A.») se rompían al pasar textos en MAYÚSCULAS a tipo título: `capitaliza()` las
  restaura.
- En las pruebas, `isVisible` no espera: después de una acción que guarda (asíncrona) usar `waitForSelector`.

## 8. Cómo ampliar

- Nuevo trámite habitual con sus días: añadirlo a `ACCIONES`.
- Otra regla de inhábiles: tocar solo `inhabil()`. Los tests de `tools/test-plazos.mjs` dicen si algo se rompe.
- Nuevo dato que leer del PDF: una expresión más en `extraer()` y un campo en el formulario.
- **Al publicar una versión nueva**: subir `CACHE` en `sw.js` (`mis-plazos-vN`) y `VERSION` en `index.html`.
- Ideas siguientes que salieron en la conversación: control de provisiones de fondos y aranceles por cliente,
  resúmenes de resoluciones con IA y borradores de escritos de trámite.

## 9. Cuenta con correo y contraseña y datos en todos los dispositivos (v1.1)

Petición: «que tenga que crearse un email y contraseña y en cualquier dispositivo que use la app se le guarde».

- **Servidor: Supabase** (Auth + Postgres + Storage), región Fráncfort. Gratis para una usuaria, cuentas con
  confirmación por correo y recuperación de contraseña de serie. Preparación en `docs/CUENTA.md` + `docs/supabase.sql`.
- **Sin librería**: la app habla con la API REST de Supabase con `fetch` (`/auth/v1/*`, `/rest/v1/registros`,
  `/storage/v1/object/pdfs/*`). Así no hay dependencia que cargar sin cobertura y se puede probar con un servidor de
  imitación (`tools/fake-supabase.mjs`).
- **Primero el dispositivo, después la nube**: IndexedDB sigue siendo la fuente de la pantalla (rápido y sin
  cobertura). Cada guardado marca un pendiente (`marcar('plazo:id' | 'kv:abogados'…)`), que se sube con un
  *upsert* por lotes; luego se bajan los registros cambiados desde el último `updated_at` (con 60 s de margen) y se
  fusionan: **gana el `updatedAt` más reciente**, y un cambio local pendiente nunca se pisa. Los borrados viajan como
  `borrado: true`.
- **Modelo en el servidor**: una sola tabla `registros (user_id, tipo, id, datos jsonb, borrado, updated_at)`;
  cada plazo es una fila y abogados, festivos y perfil una fila cada uno. RLS: `auth.uid() = user_id`. El
  `updated_at` lo pone un *trigger* con `clock_timestamp()`.
- **PDF**: Storage privado `pdfs/<usuario>/<plazo>.pdf`; se suben al sincronizar y en otro dispositivo se descargan
  al abrirlos (`obtenerPDF`).
- **Sesión**: `access_token` + `refresh_token` en IndexedDB; se renueva sola. Los enlaces de los correos (confirmar
  la cuenta, cambiar la contraseña) vuelven a la app con el token en `#…`, que `enlaceCorreo()` recoge.
- **Cerrar sesión borra los datos del dispositivo** (avisando si hay cambios sin subir). Si en el dispositivo
  había datos de antes de tener cuenta, al entrar por primera vez se suben a la cuenta.
- **Indicador** en la tarjeta de inicio: «Guardado en tu cuenta» / «Guardando…» / «Sin conexión: se guardará al
  volver».
- Si `NUBE` está vacío (o dentro del artefacto de claude.ai), la app funciona como antes, sin cuenta.

## 10. Prueba con PDF reales y formato del Tribunal de Instancia (GVA)

El usuario pasó dos notificaciones y dos escritos reales. **No se guardan en el repositorio** (datos de clientes):
se probaron en local y se crearon modelos inventados con el mismo formato (`tools/make-test-pdf.mjs <modelo>`)
que comprueba `tools/test-lectura.mjs`. Lo aprendido:

- Juzgado: «Sección … del Tribunal de Instancia de X. Plaza nº N», a veces partido en dos líneas.
- «Tipo y número de procedimiento: Juicio verbal (250.2) 321/2026» (va en minúscula y antes había que evitar que
  «Ley 6/2020» del pie de firma se tomase por el número).
- Partes con tratamientos pegados («D./Dª.Empresa Ejemplo S.L.») y partes de penal (denunciante, denunciado…).
- Título espaciado «A U T O».
- El plazo del **modo de impugnación** no es el plazo de la resolución: se ignora para el plazo principal y se ofrece
  aparte («Recurso de reforma · 3 días», «Recurso de apelación · 5 días»). Si la resolución no da plazo propio, se
  propone el primero «(si se recurre)».
- **Escritos** de la procuradora («Procuradora de los Tribunales» + «comparezco/DIGO/SUPLICO»): se avisa de que no
  abren plazo, el cliente sale de «en nombre y representación de…» y no se rellena plazo.

## 11. Redactar correos con IA

Petición: «un apartado de IA para redactar mail».

- **Claude (Anthropic) desde una Edge Function de Supabase** (`supabase/functions/redactar/index.ts`): la clave
  `ANTHROPIC_API_KEY` está en los secretos del servidor y la función solo acepta sesiones iniciadas. Modelo
  `claude-opus-5-5`, `effort: "low"`, salida estructurada `{asunto, cuerpo}` con `output_config.format`
  (`json_schema`) y `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) por si un filtro de seguridad
  rechaza la petición. SDK `@anthropic-ai/sdk@0.128.0` (comprobado con `tsc --strict`).
- **Las fechas no las decide la IA**: la app le pasa el vencimiento y el día de gracia ya calculados, y el prompt le
  prohíbe inventar fechas, importes o números.
- Pantalla «Redactar con IA» (menú, ficha del plazo y hoja de aviso): asunto, destinatario, «¿Qué quieres decir?»
  con ideas de un toque, tono cercano/formal, «Leer también el PDF» (texto sacado con pdf.js, hasta 20 000
  caracteres). El resultado es editable y se envía por correo, se comparte con el PDF o se copia.
- Seguridad de gasto: desactivar el registro de cuentas nuevas en Supabase una vez creada la suya y poner límite de
  gasto en la consola de Anthropic.

## 12. Festivos de la Comunitat Valenciana y festivos locales por juzgado (v1.2)

Confirmado: trabaja en Valencia. Se precargan los festivos oficiales, comprobados con búsqueda web (no de memoria):

| Año | Comunitat Valenciana (además de los nacionales) | València ciudad (locales) | Fuente |
|---|---|---|---|
| 2026 | 19 mar San José · 6 abr Lunes de Pascua · 24 jun San Juan · 9 oct | 22 ene San Vicente Mártir · 13 abr San Vicente Ferrer | Decreto 100/2025 (DOGV 7-7-2025); locales DOGV 14-11-2025 |
| 2027 | 19 mar · 29 mar Lunes de Pascua · 9 oct (San Juan deja de ser festivo) | 22 ene · 5 abr (pendientes de publicar en el DOGV) | Decreto 42/2026 (DOGV 25-3-2026) |

- **El Jueves Santo no es festivo en la Comunitat Valenciana**: se quitó el atajo que lo sugería.
- **Los festivos locales solo cuentan en los juzgados de su localidad** (art. 182 LOPJ). Aplicarlos a todos sería
  peligroso: en un juzgado de Picassent daría el vencimiento un día más tarde del real. Cada festivo puede llevar
  `lugar`; `inhabil(dia, urgente, organo)` solo lo aplica si el juzgado del plazo dice «… de <lugar>» (sin tildes ni
  mayúsculas, así «València» = «Valencia»), de modo que «Picassent (Valencia)» no se toma por València.
- Los oficiales están en `FESTIVOS_ZONA` y se añaden una sola vez a sus festivos (`cargarFestivosZona`, con
  `perfil.oficiales`): si borra uno, no vuelve. **Cada año**: añadir la lista nueva a `FESTIVOS_ZONA` cuando salga el
  decreto del Consell (julio) y los locales de València (noviembre), y subir la versión.
- En «Festivos» puede añadir las fiestas locales de otros pueblos con su localidad (sugiere las de sus juzgados).
- `tools/test-plazos.mjs` comprueba San José, el 9 y el 12 de octubre seguidos, San Vicente Ferrer en València sí y en
  Picassent no, y San Juan 2027.
