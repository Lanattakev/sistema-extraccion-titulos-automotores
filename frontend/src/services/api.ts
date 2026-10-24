import type { BatchDocumentResult } from '../types/documents'
import type { ReviewedVehicle, VehicleIntake } from '../types/vehicles'

const API_BASE_URL = 'http://127.0.0.1:8000/api/v1'
const textFields = [
  'id_documento', 'nombre_original', 'patente', 'marca', 'modelo',
  'numero_motor', 'numero_chasis', 'error',
] as const

function isBatchResult(value: unknown): value is BatchDocumentResult {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const item = value as Record<string, unknown>
  return textFields.every((key) => item[key] == null || typeof item[key] === 'string')
    && (item.anio == null || (typeof item.anio === 'number' && Number.isInteger(item.anio)))
    && ['requiere_revision', 'fallo'].every((key) => item[key] === undefined || typeof item[key] === 'boolean')
    && ('fallo' in item || 'id_documento' in item || 'error' in item)
}

function errorDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null || !('detail' in body)) return null
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) {
    const messages = body.detail.flatMap((item: unknown) => (
      typeof item === 'object' && item !== null && 'msg' in item && typeof item.msg === 'string'
        ? [item.msg] : []
    ))
    return messages.length ? messages.join(' · ') : null
  }
  return null
}

export async function uploadDocumentBatch(files: File[], signal?: AbortSignal): Promise<BatchDocumentResult[]> {
  if (!files.length) throw new Error('Seleccioná al menos un archivo.')
  const form = new FormData()
  files.forEach((file) => form.append('files', file))

  let response: Response
  try {
    // El navegador agrega Content-Type con el boundary del multipart.
    response = await fetch(`${API_BASE_URL}/documents/batch`, { method: 'POST', body: form, signal })
  } catch (error) {
    if (signal?.aborted) throw error
    throw new Error('No se pudo conectar con el servidor. Verificá que el backend esté disponible en http://127.0.0.1:8000 y permita conexiones desde este frontend.', { cause: error })
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(errorDetail(body) || `No se pudo procesar el lote (HTTP ${response.status}).`)
  }
  if (!Array.isArray(body) || !body.every(isBatchResult)) {
    throw new Error('El servidor devolvió una respuesta de lote inválida. No se pudieron mostrar los resultados.')
  }
  return body
}

function isVehicleIntake(value: unknown): value is VehicleIntake {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  if (typeof item.vehicle !== 'object' || item.vehicle === null) return false
  const vehicle = item.vehicle as Record<string, unknown>
  return ['patente', 'marca', 'modelo', 'numero_motor', 'numero_chasis'].every((key) => typeof vehicle[key] === 'string')
    && typeof vehicle.anio === 'number' && Number.isInteger(vehicle.anio)
    && typeof item.id_interno === 'string' && typeof item.archivo_origen === 'string'
    && typeof item.fecha_ingreso === 'string' && Number.isFinite(Date.parse(item.fecha_ingreso))
    && typeof item.requiere_revision === 'boolean'
}

async function vehicleRequest(path: string, options?: RequestInit): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch (cause) {
    throw new Error('No se pudo conectar con el backend. Verificá que esté disponible en http://127.0.0.1:8000.', { cause })
  }
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorDetail(body) || `El servidor rechazó la operación (HTTP ${response.status}).`)
  return body
}

export async function getVehicles(): Promise<VehicleIntake[]> {
  const body = await vehicleRequest('/vehicles')
  if (!Array.isArray(body) || !body.every(isVehicleIntake)) {
    throw new Error('El servidor devolvió una lista de vehículos inválida.')
  }
  return body
}

export async function confirmDocument(documentId: string, fields: ReviewedVehicle): Promise<VehicleIntake> {
  const { patente, marca, modelo, numero_motor, numero_chasis, anio } = fields
  const body = await vehicleRequest(`/documents/${encodeURIComponent(documentId)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patente, marca, modelo, numero_motor, numero_chasis, anio }),
  })
  if (!isVehicleIntake(body)) throw new Error('El servidor respondió sin una ficha válida de confirmación. Verificá Vehículos antes de volver a intentar.')
  return body
}
