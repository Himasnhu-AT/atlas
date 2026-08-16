import type { NextConfig } from 'next'

const config: NextConfig = {
  // The shared packages ship TypeScript source rather than a build, so Next
  // has to compile them the same way it compiles this app.
  transpilePackages: ['@learn/ui', '@learn/core', '@learn/learning'],

  // Off because several destinations are computed at runtime (the `?next=`
  // redirect target, lesson links built from the manifest). Typed routes would
  // force casts at every one of those, which buys nothing.
  typedRoutes: false,

  experimental: {
    // The lesson bodies are large compiled MDX strings imported at build time.
    optimizePackageImports: ['lucide-react'],
  },
}

export default config
