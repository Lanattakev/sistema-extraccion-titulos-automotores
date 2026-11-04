import type { VehicleIntake } from '../types/vehicles'
import { formatRegistrationNumber } from './registrationNumber'

const headers = ['numero_registro', 'patente', 'marca', 'modelo', 'numero_motor', 'numero_chasis', 'anio', 'archivo_origen', 'fecha_ingreso', 'requiere_revision']

function csvField(value: string | number | boolean): string {
  return `"${String(value).replace(/"/g, '""')}"`
}

export function vehiclesCsv(vehicles: VehicleIntake[]): string | null {
  if (!vehicles.length) return null
  const rows = vehicles.map(({ numero_registro, vehicle, archivo_origen, fecha_ingreso, requiere_revision }) => [
    formatRegistrationNumber(numero_registro), vehicle.patente, vehicle.marca, vehicle.modelo, vehicle.numero_motor,
    vehicle.numero_chasis, vehicle.anio, archivo_origen, fecha_ingreso, requiere_revision,
  ])
  return [headers, ...rows].map(row => row.map(csvField).join(',')).join('\r\n') + '\r\n'
}

export function downloadVehiclesCsv(vehicles: VehicleIntake[], date = new Date()): boolean {
  const csv = vehiclesCsv(vehicles)
  if (csv === null) return false
  // BOM UTF-8 para conservar tildes al abrir el archivo en hojas de cálculo.
  const blob = new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  try {
    const day = [date.getFullYear(), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
    link.href = url
    link.download = `vehiculos_${day}.csv`
    document.body.appendChild(link)
    link.click()
  } finally {
    link.remove()
    // Dar tiempo al navegador a iniciar la descarga antes de liberar el Blob.
    setTimeout(() => URL.revokeObjectURL(url), 0)
  }
  return true
}
