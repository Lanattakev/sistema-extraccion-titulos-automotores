import type { PersistedDocument } from '../types/documents'
import type { VehicleIntake } from '../types/vehicles'

export function documentMetrics(documents: PersistedDocument[]) {
  const counts = { pendiente: 0, revisado: 0, registrado: 0 }
  for (const document of documents) counts[document.estado] += 1
  const total = documents.length
  return {
    total, ...counts,
    registeredPercentage: total ? counts.registrado / total * 100 : 0,
  }
}

export function topBrands(vehicles: VehicleIntake[]) {
  const counts = new Map<string, number>()
  for (const { vehicle } of vehicles) {
    const brand = vehicle.marca.trim().replace(/\s+/g, ' ').toLocaleUpperCase('es-AR')
    if (brand) counts.set(brand, (counts.get(brand) ?? 0) + 1)
  }
  return [...counts].map(([brand, count]) => ({ brand, count }))
    .sort((a, b) => b.count - a.count || a.brand.localeCompare(b.brand, 'es-AR'))
    .slice(0, 5)
}
