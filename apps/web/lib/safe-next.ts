/**
 * Sanitize a `?next=` redirect target.
 *
 * An unchecked value here is an open redirect: `/login?next=https://evil.example`
 * would bounce a freshly authenticated user off-site. Only same-origin absolute
 * paths are allowed, and a protocol-relative `//host` is rejected because the
 * browser treats it as an absolute URL.
 */
export function safeNext(value: string | undefined, fallback = '/dashboard'): string {
  if (!value) return fallback
  if (!value.startsWith('/')) return fallback
  if (value.startsWith('//')) return fallback
  if (value.includes('\\')) return fallback
  return value
}
