import type { Env, LeadInput } from "./types";

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), {
  status,
  headers: { "content-type": "application/json; charset=utf-8" },
});

function authorized(request: Request, env: Env): boolean {
  const token = request.headers.get("authorization")?.replace(/^Bearer\s+/i, "");
  return Boolean(env.ADMIN_TOKEN && token === env.ADMIN_TOKEN);
}

async function body<T>(request: Request): Promise<T> {
  if (!request.headers.get("content-type")?.includes("application/json")) {
    throw new Error("El cuerpo debe enviarse como JSON");
  }
  return request.json<T>();
}

async function listLeads(env: Env) {
  const result = await env.DB.prepare(`
    SELECT * FROM leads
    ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
             COALESCE(next_followup_at, created_at) ASC
  `).all();
  return result.results;
}

async function createLead(request: Request, env: Env) {
  const lead = await body<LeadInput>(request);
  if (!lead.name?.trim()) return json({ error: "El nombre es obligatorio" }, 400);
  if (!lead.phone?.trim() && !lead.email?.trim()) {
    return json({ error: "Añade teléfono o correo electrónico" }, 400);
  }

  const duplicate = await env.DB.prepare(
    "SELECT id, name FROM leads WHERE (?1 <> '' AND phone = ?1) OR (?2 <> '' AND email = ?2) LIMIT 1"
  ).bind(lead.phone?.trim() || "", lead.email?.trim().toLowerCase() || "").first();
  if (duplicate) return json({ error: "Contacto duplicado", lead: duplicate }, 409);

  const result = await env.DB.prepare(`
    INSERT INTO leads (name, phone, email, source, customer_type, supply_type, status, priority, notes, consent, next_followup_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).bind(
    lead.name.trim(), lead.phone?.trim() || null, lead.email?.trim().toLowerCase() || null,
    lead.source || "manual", lead.customer_type || "unknown", lead.supply_type || "unknown",
    lead.status || "new", lead.priority || "medium", lead.notes?.trim() || "", lead.consent ? 1 : 0,
    lead.next_followup_at || null,
  ).run();

  await env.DB.prepare("INSERT INTO activities (lead_id, kind, content) VALUES (?, 'created', ?)")
    .bind(result.meta.last_row_id, `Lead creado desde ${lead.source || "manual"}`).run();
  return json({ id: result.meta.last_row_id }, 201);
}

async function updateLead(request: Request, env: Env, id: number) {
  const patch = await body<Record<string, unknown>>(request);
  const allowed = new Set(["name", "phone", "email", "source", "status", "priority", "notes", "next_followup_at", "consent", "customer_type", "supply_type"]);
  if ("name" in patch && !String(patch.name || "").trim()) return json({ error: "El nombre es obligatorio" }, 400);

  const normalized = { ...patch };
  if ("name" in normalized) normalized.name = String(normalized.name || "").trim();
  if ("phone" in normalized) normalized.phone = String(normalized.phone || "").trim() || null;
  if ("email" in normalized) normalized.email = String(normalized.email || "").trim().toLowerCase() || null;
  if ("notes" in normalized) normalized.notes = String(normalized.notes || "").trim();
  if ("next_followup_at" in normalized) normalized.next_followup_at = normalized.next_followup_at || null;

  if ("phone" in normalized || "email" in normalized) {
    const duplicate = await env.DB.prepare(
      "SELECT id, name FROM leads WHERE id <> ?3 AND ((?1 <> '' AND phone = ?1) OR (?2 <> '' AND email = ?2)) LIMIT 1"
    ).bind(String(normalized.phone || ""), String(normalized.email || ""), id).first();
    if (duplicate) return json({ error: "Ya existe otro contacto con ese teléfono o correo", lead: duplicate }, 409);
  }

  const entries = Object.entries(normalized).filter(([key]) => allowed.has(key));
  if (!entries.length) return json({ error: "No hay campos válidos" }, 400);
  const set = entries.map(([key]) => `${key} = ?`).join(", ");
  const values = entries.map(([key, value]) => key === "consent" ? (value ? 1 : 0) : value);
  await env.DB.prepare(`UPDATE leads SET ${set}, updated_at = CURRENT_TIMESTAMP WHERE id = ?`)
    .bind(...values, id).run();
  await env.DB.prepare("INSERT INTO activities (lead_id, kind, content) VALUES (?, 'updated', ?)")
    .bind(id, `Actualizado: ${entries.map(([key]) => key).join(", ")}`).run();
  return json({ ok: true });
}

async function suggestMessage(env: Env, id: number) {
  const lead = await env.DB.prepare("SELECT * FROM leads WHERE id = ?").bind(id).first<Record<string, unknown>>();
  if (!lead) return json({ error: "Lead no encontrado" }, 404);

  const prompt = `Eres el agente de captación de Berme Energy, una asesoría energética española.
Redacta un único mensaje breve, humano y nada agresivo para WhatsApp. El objetivo depende del estado:
- new/contacted: presentarse y ofrecer revisión gratuita de factura.
- interested/waiting_bill: pedir la factura completa con naturalidad.
- bill_received: confirmar recepción y explicar que se revisará.
- proposal_sent: preguntar si tiene dudas, sin presionar.
Nunca prometas ahorro, nunca pidas DNI o IBAN en este paso y no digas que somos una distribuidora.
Datos del contacto: ${JSON.stringify(lead)}
Devuelve solo el mensaje, sin título ni explicaciones.`;

  const response = await env.AI.run("@cf/meta/llama-3.1-8b-instruct-fast", {
    messages: [{ role: "user", content: prompt }],
    max_tokens: 220,
    temperature: 0.35,
  }) as { response?: string };
  return json({ message: response.response?.trim() || "" });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json({ ok: true, service: env.APP_NAME });
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    if (!authorized(request, env)) return json({ error: "No autorizado" }, 401);

    try {
      if (url.pathname === "/api/leads" && request.method === "GET") return json(await listLeads(env));
      if (url.pathname === "/api/leads" && request.method === "POST") return createLead(request, env);
      const edit = url.pathname.match(/^\/api\/leads\/(\d+)$/);
      if (edit && request.method === "PATCH") return updateLead(request, env, Number(edit[1]));
      const suggest = url.pathname.match(/^\/api\/leads\/(\d+)\/suggest-message$/);
      if (suggest && request.method === "POST") return suggestMessage(env, Number(suggest[1]));
      return json({ error: "Ruta no encontrada" }, 404);
    } catch (error) {
      return json({ error: error instanceof Error ? error.message : "Error inesperado" }, 500);
    }
  },
} satisfies ExportedHandler<Env>;
