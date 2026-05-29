import { createContext, useContext, useState, useCallback, useMemo, useEffect, useRef } from 'react'
import ToastContainer from '../components/shared/ToastContainer'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timerIds = useRef(new Map())

  useEffect(() => {
    const timers = timerIds.current
    return () => timers.forEach((id) => clearTimeout(id))
  }, [])

  const addToast = useCallback((variant, title, message = '') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev, { id, variant, title, message }].slice(-3))
    const timerId = setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
      timerIds.current.delete(id)
    }, 4000)
    timerIds.current.set(id, timerId)
  }, [])

  const dismiss = useCallback((id) => {
    const timerId = timerIds.current.get(id)
    if (timerId) { clearTimeout(timerId); timerIds.current.delete(id) }
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useMemo(() => ({
    success: (title, message) => addToast('success', title, message),
    error:   (title, message) => addToast('error',   title, message),
    info:    (title, message) => addToast('info',    title, message),
    warning: (title, message) => addToast('warning', title, message),
  }), [addToast])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
