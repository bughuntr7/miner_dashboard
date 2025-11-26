'use client'

import { createContext, useContext, useState, ReactNode } from 'react'
import Alert, { AlertType } from './Alert'

interface AlertState {
  id: string
  type: AlertType
  message: string
  duration?: number
}

interface AlertContextType {
  showAlert: (type: AlertType, message: string, duration?: number) => void
  clearAlerts: () => void
}

const AlertContext = createContext<AlertContextType | undefined>(undefined)

export function useAlerts() {
  const context = useContext(AlertContext)
  if (!context) {
    throw new Error('useAlerts must be used within AlertProvider')
  }
  return context
}

export function AlertProvider({ children }: { children: ReactNode }) {
  const [alerts, setAlerts] = useState<AlertState[]>([])

  const showAlert = (type: AlertType, message: string, duration?: number) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9)
    setAlerts(prev => [...prev, { id, type, message, duration }])
  }

  const removeAlert = (id: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== id))
  }

  const clearAlerts = () => {
    setAlerts([])
  }

  return (
    <AlertContext.Provider value={{ showAlert, clearAlerts }}>
      {children}
      <div className="fixed top-4 right-4 z-50 w-full max-w-md space-y-2">
        {alerts.map(alert => (
          <Alert
            key={alert.id}
            type={alert.type}
            message={alert.message}
            duration={alert.duration}
            onClose={() => removeAlert(alert.id)}
          />
        ))}
      </div>
    </AlertContext.Provider>
  )
}

