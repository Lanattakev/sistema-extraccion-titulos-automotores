import type { VehicleIntake } from '../types/vehicles'

export function searchVehicles(vehicles: VehicleIntake[], query: string): VehicleIntake[] {
  const term = query.trim().toLocaleUpperCase('es-AR')
  if (!term) return vehicles
  const numeric = /^\d+$/.test(term) ? Number(term) : null
  return vehicles.filter(intake => numeric !== null ? intake.numero_registro === numeric
    : intake.vehicle.patente.toLocaleUpperCase('es-AR').includes(term))
}
