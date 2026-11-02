/** The public origin. Overridable so a preview or self-hosted copy links to itself. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://atlas.himanshuat.com').replace(
  /\/$/,
  '',
)
