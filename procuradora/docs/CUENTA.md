# Activar la cuenta (correo y contraseña) y la IA

La app ya está preparada. Falta crear el «servidor» donde se guardan las cuentas y los datos. Se usa **Supabase**
(gratis para este uso). Se hace una vez y tarda unos 15 minutos.

Mientras no se haga, la app sigue funcionando como antes: sin cuenta y con los datos solo en el móvil.

## 1. Crear el proyecto

1. Entra en **supabase.com** → *Start your project* → regístrate (vale con la cuenta de GitHub).
2. **New project**:
   - Name: `mis-plazos`
   - Database password: una contraseña larga (guárdala; la app no la usa).
   - Region: **Central EU (Frankfurt)**, para que los datos estén en la Unión Europea.
3. Espera a que termine de crearse (1–2 minutos).

## 2. Preparar la base de datos

1. Menú izquierdo → **SQL Editor** → *New query*.
2. Pega entero el contenido de [`supabase.sql`](supabase.sql) y pulsa **Run**. Debe decir *Success*.

Esto crea la tabla de datos, el almacén privado de PDF y las reglas para que **cada cuenta solo vea lo suyo**.

## 3. Correos de la cuenta

1. **Authentication → URL Configuration**:
   - *Site URL*: `https://ai-phi-design.github.io/PHI.BET/procuradora/`
   - *Redirect URLs*: añade la misma dirección.
2. **Authentication → Sign In / Providers → Email**: deja activado *Confirm email*. Así, al crear la cuenta llega un
   correo para confirmarla, y si algún día olvida la contraseña puede recuperarla por correo.

## 4. Conectar la app

1. **Project Settings → API** (o *Data API*). Copia:
   - **Project URL** (algo como `https://abcdefgh.supabase.co`)
   - **anon public key** (una clave larga que empieza por `eyJ…`, o `sb_publishable_…`)
2. Pásaselas a Claude para que las ponga en la app, o escríbelas tú en `index.html`, en la línea
   `const NUBE = { url: '', key: '' };`. La clave *anon* es pública por diseño; lo que protege los datos son las
   reglas del paso 2. **Nunca** pongas ahí la clave *service_role*.
3. Sube el número de versión (`VERSION` en `index.html` y `CACHE` en `sw.js`) y publica.

## 5. Crear la cuenta de tu madre y cerrar la puerta

1. Abre la app → **Crear cuenta** → su correo y una contraseña → confirma desde el correo que le llega.
2. Ya con su cuenta creada: **Authentication → Sign In / Providers → desactiva _Allow new users to sign up_**.
   Así nadie más puede crearse una cuenta en tu proyecto (ni gastar la IA).

En cada dispositivo nuevo solo tiene que abrir la app y **Entrar** con su correo y contraseña.

## 6. IA para redactar correos (opcional)

La IA es Claude, de Anthropic. La app no guarda la clave: la usa una pequeña función del servidor.

1. Crea una clave en **platform.claude.com** → *API Keys* → *Create Key*. En *Billing* pon un límite de gasto
   mensual (por ejemplo 10 €). Cada correo cuesta unos pocos céntimos.
2. En Supabase → **Edge Functions → Secrets** → añade `ANTHROPIC_API_KEY` con esa clave.
3. **Edge Functions → Deploy a new function → Via Editor** → nombre **`redactar`** → pega el contenido de
   [`../supabase/functions/redactar/index.ts`](../supabase/functions/redactar/index.ts) → *Deploy*.
   (Con la línea de comandos: `supabase functions deploy redactar` y `supabase secrets set ANTHROPIC_API_KEY=…`.)
4. Deja activado *Verify JWT* (viene así): solo se puede usar con una sesión iniciada en la app.

## Bueno saber

- **Privacidad**: los datos viajan cifrados y cada cuenta solo ve lo suyo. Quien administra el proyecto de Supabase
  (tú) sí puede verlos desde el panel. Al usar la IA, los datos del asunto y el texto del PDF se envían a Anthropic
  para redactar el correo; por defecto no se usan para entrenar modelos.
- **Plan gratuito**: si el proyecto pasa 7 días sin ningún uso, Supabase lo pausa (se reactiva desde el panel). Con
  uso diario no pasa.
- **Correos de Supabase**: el servicio de correo que trae de serie envía pocos mensajes por hora; para una sola
  cuenta es suficiente.
