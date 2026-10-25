import { useCallback, useEffect, useRef, useState } from 'react'
import { getHistory } from '../services/api'
import type { HistoryEvent, HistoryState } from '../types/history'

export function useHistory(): HistoryState {
  const [events, setEvents] = useState<HistoryEvent[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestNumber = useRef(0)

  const receive = useCallback((request: number, saved: HistoryEvent[]) => {
    if (request !== requestNumber.current) return
    setEvents(saved)
    setError(null)
    setLoading(false)
  }, [])

  const reject = useCallback((request: number, cause: unknown) => {
    if (request !== requestNumber.current) return
    setEvents(null)
    setError(cause instanceof Error ? cause.message : 'No se pudo recuperar el historial.')
    setLoading(false)
  }, [])

  const refresh = useCallback(async () => {
    const request = ++requestNumber.current
    setLoading(true)
    setError(null)
    try {
      receive(request, await getHistory())
    } catch (cause) {
      reject(request, cause)
    }
  }, [receive, reject])

  useEffect(() => {
    const request = ++requestNumber.current
    getHistory().then(saved => receive(request, saved), (cause: unknown) => reject(request, cause))
    return () => { requestNumber.current += 1 }
  }, [receive, reject])

  return { events, loading, error, refresh }
}
