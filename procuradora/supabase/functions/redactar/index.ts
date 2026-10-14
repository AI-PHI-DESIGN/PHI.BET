// Función «redactar» (Supabase Edge Function): escribe con Claude el correo de la procuradora al abogado o al cliente.
// La clave de Anthropic vive en los secretos de Supabase (ANTHROPIC_API_KEY): la app nunca la ve.
// Supabase solo deja llamar a esta función con una sesión iniciada (comprueba el token antes de ejecutarla).
// Publicarla: ver docs/CUENTA.md (paso «IA para redactar correos»).
import Anthropic from "npm:@anthropic-ai/sdk@0.128.0";

const client = new Anthropic(); // lee ANTHROPIC_API_KEY del entorno

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const SISTEMA = `Eres el asistente de una procuradora de los tribunales en España. Redactas correos electrónicos en su nombre, en español de España, normalmente para el abogado del asunto y a veces para el cliente.

- Usa solo los datos que te den (juzgado, procedimiento, partes, fechas, plazos). No inventes fechas, importes, nombres ni números de procedimiento. Las fechas de vencimiento ya vienen calculadas: cópialas tal cual.
- Si te pasan el texto de la resolución, resume en una o dos frases lo que acuerda, en lenguaje claro.
- Correo breve y profesional: saludo, lo esencial, qué se necesita y para cuándo, y despedida con la firma que te den.
- Tono «formal»: de usted. Tono «cercano»: de tú, cordial, sin coloquialismos.
- Texto plano listo para pegar en un correo: sin markdown, sin asteriscos y sin viñetas con símbolos.`;

const ESQUEMA = {
  type: "object",
  properties: { asunto: { type: "string" }, cuerpo: { type: "string" } },
  required: ["asunto", "cuerpo"],
  additionalProperties: false,
};

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...CORS, "Content-Type": "application/json" } });

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
  if (req.method !== "POST") return json(405, { error: "Método no permitido" });

  let datos: Record<string, unknown>;
  try { datos = await req.json(); } catch { return json(400, { error: "Petición no válida" }); }
  const peticion = String(datos.peticion ?? "").trim().slice(0, 2000);
  const contexto = String(datos.contexto ?? "").slice(0, 6000);
  const resolucion = String(datos.resolucion ?? "").slice(0, 20000);
  const tono = datos.tono === "cercano" ? "cercano" : "formal";
  if (!peticion) return json(400, { error: "Escribe qué quieres decir en el correo." });

  const mensaje = [
    `Tono: ${tono}.`,
    `Lo que quiere decir: ${peticion}`,
    contexto && `Datos del asunto:\n${contexto}`,
    resolucion && `Texto de la resolución (sacado del PDF):\n${resolucion}`,
  ].filter(Boolean).join("\n\n");

  try {
    const r = await client.beta.messages.create({
      model: "claude-opus-5-5",
      max_tokens: 8000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "low", format: { type: "json_schema", schema: ESQUEMA } },
      system: SISTEMA,
      messages: [{ role: "user", content: mensaje }],
    });
    if (r.stop_reason === "refusal") return json(422, { error: "La IA no ha querido redactar este correo. Prueba a explicarlo de otra forma." });
    if (r.stop_reason === "max_tokens") return json(502, { error: "El correo ha salido demasiado largo. Pide uno más breve." });
    const bloque = r.content.find((b) => b.type === "text");
    if (!bloque || bloque.type !== "text") return json(502, { error: "La IA no ha devuelto texto. Prueba otra vez." });
    const salida = JSON.parse(bloque.text) as { asunto: string; cuerpo: string };
    return json(200, { asunto: salida.asunto, cuerpo: salida.cuerpo });
  } catch (e) {
    if (e instanceof Anthropic.RateLimitError) return json(429, { error: "Demasiadas peticiones seguidas. Espera un minuto." });
    if (e instanceof Anthropic.AuthenticationError) return json(500, { error: "La clave de la IA no está bien configurada en el servidor." });
    if (e instanceof Anthropic.APIError) return json(502, { error: "La IA no está disponible ahora mismo. Prueba en un rato." });
    if (e instanceof SyntaxError) return json(502, { error: "La respuesta de la IA no se pudo leer. Prueba otra vez." });
    throw e;
  }
});
