import Link from 'next/link'
import type { ReactNode } from 'react'

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-rule">
        <div className="mx-auto w-full max-w-page px-6 py-5 sm:px-8">
          <Link href="/" className="font-serif text-[17px] font-medium text-ink">
            Atlas
          </Link>
        </div>
      </header>

      <main id="main" className="flex flex-1 items-center px-6 py-20 sm:px-8">
        <div className="mx-auto w-full max-w-page">{children}</div>
      </main>
    </div>
  )
}
