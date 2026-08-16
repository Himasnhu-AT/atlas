import {
  ApiError,
  type NewAttempt,
  ProgressSnapshot,
  type SaveExerciseCode,
  type UpdateLessonProgress,
  User,
  type ExerciseState,
} from './types'
import { z } from 'zod'

/**
 * The typed client both apps use to talk to the Next.js API.
 *
 * The web app calls it with same-origin cookies. The desktop app calls it with
 * a bearer token from device pairing and an absolute base URL. Nothing else
 * differs, which is the point of putting it here rather than in either app.
 */

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly detail?: string,
  ) {
    super(detail ? `${status}: ${detail}` : `request failed with ${status}`)
    this.name = 'ApiRequestError'
  }

  /** The caller should send the user to sign in again. */
  get isAuthFailure(): boolean {
    return this.status === 401 || this.status === 403
  }

  /** Worth retrying: the request may succeed unchanged. */
  get isTransient(): boolean {
    return this.status === 408 || this.status === 429 || this.status >= 500
  }
}

export interface ApiClientOptions {
  /** Empty for same-origin web requests; an absolute origin on desktop. */
  baseUrl?: string
  /** Supplies a bearer token. Async so desktop can read the OS keychain. */
  getToken?: () => string | undefined | Promise<string | undefined>
  fetchImpl?: typeof fetch
}

export class ApiClient {
  private readonly baseUrl: string
  private readonly getToken?: ApiClientOptions['getToken']
  private readonly fetchImpl: typeof fetch

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? '').replace(/\/$/, '')
    this.getToken = options.getToken
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis)
  }

  private async request<T>(
    path: string,
    schema: z.ZodType<T>,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers)
    headers.set('accept', 'application/json')
    if (init.body !== undefined) headers.set('content-type', 'application/json')

    const token = await this.getToken?.()
    if (token) headers.set('authorization', `Bearer ${token}`)

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      // Same-origin cookies carry the web session. Harmless on desktop, where
      // the bearer token does the work.
      credentials: 'include',
    })

    if (!response.ok) {
      throw new ApiRequestError(response.status, await readErrorDetail(response))
    }

    if (response.status === 204) return schema.parse(undefined)

    // Validate at the boundary. A server that starts returning a different
    // shape should fail here, loudly, rather than three components later.
    return schema.parse(await response.json())
  }

  me(): Promise<User> {
    return this.request('/api/me', User)
  }

  progress(): Promise<ProgressSnapshot> {
    return this.request('/api/progress', ProgressSnapshot)
  }

  updateLessonProgress(body: UpdateLessonProgress): Promise<ProgressSnapshot> {
    return this.request('/api/progress', ProgressSnapshot, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  }

  saveExerciseCode(body: SaveExerciseCode): Promise<void> {
    return this.request('/api/exercises/state', z.void(), {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  }

  exerciseState(exerciseId: string): Promise<ExerciseState | null> {
    return this.request(
      `/api/exercises/state?exerciseId=${encodeURIComponent(exerciseId)}`,
      z.custom<ExerciseState | null>(),
    )
  }

  recordAttempt(body: NewAttempt): Promise<void> {
    return this.request('/api/attempts', z.void(), {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  /** The manifest the desktop app diffs against its bundled copy. */
  contentManifest(): Promise<{ contentVersion: string; modules: unknown[] }> {
    return this.request(
      '/api/content/manifest',
      z.object({ contentVersion: z.string(), modules: z.array(z.unknown()) }),
    )
  }
}

async function readErrorDetail(response: Response): Promise<string | undefined> {
  try {
    const parsed = ApiError.safeParse(await response.json())
    return parsed.success ? (parsed.data.detail ?? parsed.data.error) : undefined
  } catch {
    return undefined
  }
}
