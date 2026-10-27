import { NextRequest, NextResponse } from 'next/server';

const BACKEND =
  process.env.AGRIMARKET_API_URL ||
  process.env.AGRIMARKET_BACKEND_URL ||
  'http://127.0.0.1:5000';

async function forward(request: NextRequest, context: { params: Promise<{path:string[]}> }) {
  const {path} = await context.params;
  const target = `${BACKEND}/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`;
  try {
    const response = await fetch(target, {
      method: request.method,
      headers: {'Content-Type':'application/json'},
      cache: 'no-store',
      ...(request.method === 'GET' || request.method === 'HEAD'
        ? {}
        : {body: await request.text()})
    });
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('content-type') || 'application/json',
        'Cache-Control':'no-store'
      }
    });
  } catch {
    return NextResponse.json(
      {error:'Could not reach the AgriMarket Flask backend.', backend:BACKEND},
      {status:502}
    );
  }
}

export const GET = forward;
export const POST = forward;
