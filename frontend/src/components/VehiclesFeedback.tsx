import type { VehiclesState } from '../types/vehicles'

export function VehiclesFeedback({ loading, error, refresh }: VehiclesState) {
  if (loading) return <p className="vehicle-feedback" role="status">Actualizando vehículos…</p>
  if (error) return <div className="batch-alert" role="alert"><p><strong>No se pudo actualizar el registro.</strong> {error}</p><button type="button" className="text-button" onClick={() => void refresh()}>Reintentar consulta</button></div>
  return null
}
