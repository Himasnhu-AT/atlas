import { Analytics } from '@vercel/analytics/next'
import type { Metadata } from 'next'
import type { ReactNode } from 'react'

import { SITE_URL } from '@/lib/site'

import './globals.css'

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Atlas',
    template: '%s · Atlas',
  },
  description:
    'Code-first engineering courses. Read the lesson, write the code, run the tests in an isolated sandbox.',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    /*
     * `data-scroll-behavior` stops Next warning about the smooth scrolling set
     * in globals.css during route transitions.
     *
     * There is no theme script here any more. The product has one theme, so
     * there is nothing to restore before paint and no flash to prevent.
     */
    <html lang="en" data-scroll-behavior="smooth">
      <body className="min-h-screen bg-paper text-ink">
        <a
          href="#main"
          className="sr-only rounded-field bg-ink px-5 text-caption font-medium text-paper focus:inline-flex focus:min-h-11 focus:items-center focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
        >
          Skip to content
        </a>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
