import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const apiBase =
    process.env.AGRIMARKET_API_URL ??
    process.env.AGRIMARKET_BACKEND_URL ??
    process.env.API_BASE_URL ??
    "http://127.0.0.1:5000";

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON." }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${apiBase.replace(/\/$/, "")}/api/ai/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  } catch {
    return Response.json(
      { error: "Could not connect to the Flask API. Start the backend on port 5000." },
      { status: 502 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const body = await upstream.text().catch(() => "");
    return new Response(body || JSON.stringify({ error: "The backend could not start the workflow." }), {
      status: upstream.status || 502,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
