import 'server-only'

import { NextResponse } from 'next/server'
import { ZodError, type ZodType } from 'zod'

import { UnauthorizedError } from './session'

/**
 * Uniform JSON responses and error mapping, so every route handler stays short
 * and no handler invents its own error shape.
 */

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

export class NotFoundError extends Error {
  constructor(detail = 'not found') {
    super(detail)
    this.name = 'NotFoundError'
  }
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
    try {
      return await handler(request, context)
    } catch (error) {
      if (error instanceof UnauthorizedError) return fail(401, 'unauthorized')
      if (error instanceof BadRequestError) return fail(400, 'bad_request', error.message)
      if (error instanceof NotFoundError) return fail(404, 'not_found', error.message)
      if (error instanceof ZodError) {
        const first = error.issues[0]
        return fail(
          422,
          'validation_failed',
          first ? `${first.path.join('.') || 'body'}: ${first.message}` : undefined,
        )
      }

      console.error('unhandled route error', error)
      return fail(500, 'internal_error')
    }
  }
}
