'use client'

import { AlertProvider } from './AlertContainer'

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <AlertProvider>
      {children}
    </AlertProvider>
  )
}

