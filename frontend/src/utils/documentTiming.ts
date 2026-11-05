import type { BatchDocumentResult, PersistedDocument } from '../types/documents'
import type { HistoryEvent } from '../types/history'
import type { ConfirmationState } from '../types/vehicles'

export type DocumentFilter = 'todos' | PersistedDocument['estado']
export type AgeOrder = 'oldest' | 'newest'
export type PriorityOrder = 'normal' | 'high' | 'low'

export function nextPriorityOrder(order: PriorityOrder): PriorityOrder {
  return order === 'normal' ? 'high' : order === 'high' ? 'low' : 'normal'
}

export function orderByPriority<T>(rows: T[], order: PriorityOrder,
  status: (row: T) => PersistedDocument['estado'] | null, loadedAt: (row: T) => number | undefined): T[] {
  if (order === 'normal') return [...rows]
  const priority = { pendiente: 0, revisado: 1, registrado: 2 }
  const direction = order === 'high' ? 1 : -1
  return [...rows].sort((a, b) => {
    const firstStatus = status(a)
    const secondStatus = status(b)
    if (firstStatus === null) return secondStatus === null ? 0 : 1
    if (secondStatus === null) return -1
    const difference = priority[firstStatus] - priority[secondStatus]
    if (difference) return direction * difference
    const first = loadedAt(a)
    const second = loadedAt(b)
    if (first === undefined) return second === undefined ? 0 : 1
    if (second === undefined) return -1
    return direction * (first - second)
  })
}

export function documentLoadTimes(events: HistoryEvent[], now: Date): Map<string, number> {
  const loaded = new Map<string, number>()
  for (const event of events) {
    const time = Date.parse(event.fecha_evento)
    if (event.tipo_evento !== 'documento_cargado' || !Number.isFinite(time) || time > now.getTime()) continue
    loaded.set(event.id_documento, Math.min(loaded.get(event.id_documento) ?? time, time))
  }
  return loaded
}

export function documentAge(id: string | null | undefined, loaded: Map<string, number>, now: Date): number | null {
  const time = id ? loaded.get(id) : undefined
  return time === undefined ? null : now.getTime() - time
}

export function documentReviewTimes(events: HistoryEvent[], loaded: Map<string, number>, now: Date): Map<string, number> {
  const reviewed = new Map<string, number>()
  for (const event of events) {
    const start = loaded.get(event.id_documento)
    const time = Date.parse(event.fecha_evento)
    if (event.tipo_evento !== 'documento_revisado' || start === undefined
      || !Number.isFinite(time) || time < start || time > now.getTime()) continue
    reviewed.set(event.id_documento, Math.min(reviewed.get(event.id_documento) ?? time, time))
  }
  return reviewed
}

export function documentAging(id: string | null | undefined, status: PersistedDocument['estado'] | null,
  loaded: Map<string, number>, reviewed: Map<string, number>, now: Date): number | null {
  const start = id ? loaded.get(id) : undefined
  if (start === undefined || status === null) return null
  if (status === 'pendiente') return now.getTime() - start
  const end = reviewed.get(id!)
  return end === undefined ? null : end - start
}

export function documentAgingLabel(id: string | null | undefined, status: PersistedDocument['estado'] | null,
  loaded: Map<string, number>, reviewed: Map<string, number>, now: Date): string {
  if (!id || !loaded.has(id)) return 'Sin fecha de carga'
  if (status === null) return 'Tiempo no disponible'
  const aging = documentAging(id, status, loaded, reviewed, now)
  return aging === null ? 'Sin fecha de revisión' : formatDuration(aging)
}

export function formatDuration(milliseconds: number | null): string {
  if (milliseconds === null || !Number.isFinite(milliseconds) || milliseconds < 0) return 'Sin fecha de carga'
  const minutes = Math.floor(milliseconds / 60_000)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} h`
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  return `${days} ${days === 1 ? 'día' : 'días'}${remainingHours ? ` ${remainingHours} h` : ''}`
}

export function resultStatus(result: BatchDocumentResult, confirmations: Record<string, ConfirmationState>, persisted: PersistedDocument[]) {
  if (!result.id_documento || result.fallo || result.error) return null
  const state = confirmations[result.id_documento]
  if (state?.registered) return 'registrado'
  if (state?.reviewed) return 'revisado'
  if (state?.dirty) return 'pendiente'
  return persisted.find(document => document.id_documento === result.id_documento)?.estado ?? 'pendiente'
}

export function filterAndOrderDocuments<T extends BatchDocumentResult>(results: T[], filter: DocumentFilter,
  order: AgeOrder, loaded: Map<string, number>, confirmations: Record<string, ConfirmationState>, persisted: PersistedDocument[]): T[] {
  return filterAndPrioritizeDocuments(results, filter, order === 'oldest' ? 'high' : 'low', loaded, confirmations, persisted)
}

export function filterAndPrioritizeDocuments<T extends BatchDocumentResult>(results: T[], filter: DocumentFilter,
  order: PriorityOrder, loaded: Map<string, number>, confirmations: Record<string, ConfirmationState>, persisted: PersistedDocument[]): T[] {
  return orderByPriority(results.filter(result => filter === 'todos' || resultStatus(result, confirmations, persisted) === filter),
    order, result => resultStatus(result, confirmations, persisted), result => result.id_documento ? loaded.get(result.id_documento) : undefined)
}
