# Mis Plazos · agenda de plazos para procuradores

App para el móvil que ayuda a una procuradora a no perder ningún plazo:

1. **Sube la notificación de LexNET** (el PDF). La app lee el juzgado, el procedimiento, las partes, la resolución,
   la fecha de la carátula y el plazo («en el plazo de cinco días…»).
2. **Calcula el vencimiento en días hábiles**: fines de semana, festivos nacionales, los festivos que añadas de tu
   comunidad y tu localidad, agosto y del 24 de diciembre al 6 de enero. Enseña el paso a paso y el día de gracia
   (hasta las 15:00 del día hábil siguiente).
3. **Te avisa de lo urgente**: en rojo lo que vence hoy, en ámbar lo que vence en 3 días hábiles o menos y en verde
   lo que va con tiempo.
4. **Avisa al abogado** con un correo ya redactado, o por WhatsApp con el PDF adjunto.
5. **Exporta al calendario del móvil** (.ics) con aviso a las 9:00 dos días antes y el día anterior.

Todo se guarda **en el propio móvil** (no se envía a ningún servidor). Desde el menú se puede guardar una copia de
seguridad y recuperarla.

## Dirección de la app

`https://ai-phi-design.github.io/PHI.BET/procuradora/`

Para que funcione, GitHub Pages tiene que estar activado: **Settings → Pages → Source: Deploy from a branch →**
la rama que contiene esta carpeta, carpeta `/ (root)` **→ Save**.

### Instalarla en el móvil

- **Android (Chrome):** abrir la dirección → menú ⋮ → *Instalar aplicación*.
- **iPhone (Safari):** abrir la dirección → botón Compartir → *Añadir a pantalla de inicio*.

Una vez instalada funciona sin cobertura, y las versiones nuevas llegan solas.

## Lo primero al estrenarla

1. Escribir tu nombre (sale en el saludo y en la firma de los avisos).
2. Menú ☰ → **Festivos**: añadir los festivos de tu comunidad autónoma y de tu localidad de este año.
3. Menú ☰ → **Abogados**: añadir a los abogados con su correo y teléfono.

> La app ayuda a no olvidar los plazos, pero la última palabra la tiene la procuradora: hay que revisar siempre el
> plazo que dice la resolución.

## Pruebas

```bash
node tools/test-plazos.mjs     # casos de cálculo (puente, 15:00, sábado, agosto, Navidad, meses, Semana Santa, festivo local)
node tools/e2e.mjs shots       # de punta a punta en un móvil simulado, con capturas en shots/
SCHEME=dark node tools/e2e.mjs shots
node tools/e2e-update.mjs      # versión nueva con la app instalada y arranque sin cobertura
```

Cómo se construyó, y cómo repetirlo: [`docs/COMO-SE-HIZO.md`](docs/COMO-SE-HIZO.md).
