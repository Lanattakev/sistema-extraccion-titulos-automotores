import { useCallback, useEffect, useRef, useState } from 'react'
import { getVehicles } from '../services/api'
import type { VehicleIntake, VehiclesState } from '../types/vehicles'

export function useVehicles(): VehiclesState {
  const [vehicles, setVehicles] = useState<VehicleIntake[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const requestNumber = useRef(0)

  const receive = useCallback((request: number, saved: VehicleIntake[]) => {
    if (request !== requestNumber.current) return
    setVehicles(saved)
    setError(null)
    setLoading(false)
  }, [])

  const reject = useCallback((request: number, cause: unknown) => {
    if (request !== requestNumber.current) return
    setVehicles(null)
    setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los vehículos.')
    setLoading(false)
  }, [])

  const refresh = useCallback(async () => {
    const request = ++requestNumber.current
    setLoading(true)
    setError(null)
    try {
      receive(request, await getVehicles())
    } catch (cause) {
      reject(request, cause)
    }
  }, [receive, reject])

  useEffect(() => {
    const request = ++requestNumber.current
    getVehicles().then((saved) => receive(request, saved), (cause: unknown) => reject(request, cause))
    return () => { requestNumber.current += 1 }
  }, [receive, reject])

  return { vehicles, loading, error, refresh }
}
