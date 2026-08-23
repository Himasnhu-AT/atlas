import 'server-only'

import { NextResponse } from 'next/server'
import { ZodError, type ZodType } from 'zod'

import { refreshedTokenFor, UnauthorizedError } from './session'

/**
 * Uniform JSON responses and error mapping, so every route handler stays short
 * and no handler invents its own error shape.
 */

/**
 * Origins allowed to call this API with credentials.
 *
 * The desktop app's webview has its own origin, and nothing here had ever set a
 * CORS header because nothing had ever needed one: the app's only request was a
 * fire-and-forget PUT that failed silently. The moment it sends an
 * `Authorization` header the request stops being simple, a preflight goes out,
 * and every call fails.
 *
 * Allow-listed rather than reflected, and never `*`: these responses carry a
 * session, and `*` is not permitted with credentials anyway.
 */
const ALLOWED_ORIGINS = new Set([
  // Tauri serves the bundled app from a custom scheme. macOS and Linux use the
  // first; Windows uses the second.
  'tauri://localhost',
  'http://tauri.localhost',
  // The desktop UI running in a browser under `pnpm dev:desktop:web`.
  'http://localhost:5174',
])

const ALLOWED_HEADERS = 'authorization, content-type, idempotency-key'

/**
 * Where a replacement session token is delivered.
 *
 * A header rather than the body, because every route would otherwise have to
 * remember to include it and one that forgot would quietly stop refreshing.
 */
export const REFRESH_HEADER = 'x-atlas-session'

function corsHeaders(request: Request): Record<string, string> {
  const origin = request.headers.get('origin')
  if (!origin || !ALLOWED_ORIGINS.has(origin)) return {}
  return {
    'access-control-allow-origin': origin,
    'access-control-allow-credentials': 'true',
    // A cross-origin caller cannot read a response header it was not told
    // about, and the desktop has to read this one to keep its session alive.
    'access-control-expose-headers': REFRESH_HEADER,
    // The response varies by origin, so a cache must not serve one origin's
    // headers to another.
    vary: 'Origin',
  }
}

export function json<T>(data: T, status = 200): NextResponse {
  return NextResponse.json(data as object, { status })
}

export function fail(status: number, error: string, detail?: string): NextResponse {
  return NextResponse.json({ error, detail }, { status })
}

/**
 * Parse and validate a JSON body.
 *
 * Anything not in the schema is dropped, which is how a `userId` smuggled into
 * a request body gets ignored rather than trusted.
 */
export async function parseBody<T>(request: Request, schema: ZodType<T>): Promise<T> {
  let raw: unknown
  try {
    raw = await request.json()
  } catch {
    throw new BadRequestError('request body was not valid JSON')
  }
  return schema.parse(raw)
}

export class BadRequestError extends Error {
  constructor(detail: string) {
    super(detail)
    this.name = 'BadRequestError'
  }
}

export class ForbiddenError extends Error {
  constructor(detail = 'not allowed') {
    super(detail)
    this.name = 'ForbiddenError'
  }
}

export class NotFoundError extends Error {
  constructor(detail = 'not found') {
    super(detail)
    this.name = 'NotFoundError'
  }
}

/**
 * The preflight every route gets for free.
 *
 * Export it as `OPTIONS` from any handler the desktop app calls:
 * `export const OPTIONS = preflight`.
 */
export function preflight(request: Request): Response {
  const headers = corsHeaders(request)
  if (Object.keys(headers).length === 0) return new Response(null, { status: 403 })
  return new Response(null, {
    status: 204,
    headers: {
      ...headers,
      'access-control-allow-methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'access-control-allow-headers': ALLOWED_HEADERS,
      'access-control-max-age': '86400',
    },
  })
}

/** Wrap a handler so thrown errors become the right status instead of a 500. */
export function route(
  handler: (
    request: Request,
    context: { params: Promise<Record<string, string>> },
  ) => Promise<Response>,
) {
  return async (
    request: Request,
    context: { params: Promise<Record<string, string>> },
  ): Promise<Response> => {
    const cors = corsHeaders(request)
    const withCors = (response: Response): Response => {
      for (const [key, value] of Object.entries(cors)) response.headers.set(key, value)
      return response
    }

    try {
      const response = withCors(await handler(request, context))

      // Slide the session window on a request that actually succeeded. A paired
      // desktop in daily use then never runs into the thirty day expiry it was
      // issued with, and one that has been closed for a month still expires on
      // schedule. Skipped on a 401 so a token whose account has been deleted or
      // revoked is not handed a fresh one on the way out.
      if (response.status !== 401) {
        const refreshed = refreshedTokenFor(request)
        if (refreshed) response.headers.set(REFRESH_HEADER, refreshed.token)
      }

      return response
    } catch (error) {
      if (error instanceof UnauthorizedError) return withCors(fail(401, 'unauthorized'))
      if (error instanceof BadRequestError)
        return withCors(fail(400, 'bad_request', error.message))
      if (error instanceof ForbiddenError)
        return withCors(fail(403, 'forbidden', error.message))
      if (error instanceof NotFoundError) return withCors(fail(404, 'not_found', error.message))
      if (error instanceof ZodError) {
        const first = error.issues[0]
        return withCors(
          fail(
            422,
            'validation_failed',
            first ? `${first.path.join('.') || 'body'}: ${first.message}` : undefined,
          ),
        )
      }

      console.error('unhandled route error', error)
      return withCors(fail(500, 'internal_error'))
    }
  }
}
