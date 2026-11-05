import type { PersistedDocument } from '../types/documents'
import type { VehicleIntake } from '../types/vehicles'

export type RegistryRow = {
  key: string
  status: PersistedDocument['estado']
  document?: PersistedDocument
  intake?: VehicleIntake
}

export function registryRows(documents: PersistedDocument[], vehicles: VehicleIntake[]): RegistryRow[] {
  const byId = new Map(vehicles.map(vehicle => [vehicle.id_interno, vehicle]))
  const linked = new Set<string>()
  const rows: RegistryRow[] = documents.map(document => {
    const intake = document.id_interno ? byId.get(document.id_interno) : undefined
    if (intake) linked.add(intake.id_interno)
    return { key: `document:${document.id_documento}`, status: document.estado, document, intake }
  })
  for (const intake of vehicles) {
    if (!linked.has(intake.id_interno)) rows.push({ key: `vehicle:${intake.id_interno}`, status: 'registrado', intake })
  }
  return rows
}

export function searchRegistryRows(rows: RegistryRow[], query: string): RegistryRow[] {
  const term = query.trim().toLocaleUpperCase('es-AR')
  if (!term) return rows
  const numeric = /^\d+$/.test(term) ? Number(term) : null
  return rows.filter(row => numeric !== null ? row.intake?.numero_registro === numeric
    : (row.intake?.vehicle.patente ?? row.document?.patente ?? '').toLocaleUpperCase('es-AR').includes(term))
}
