import type { HistoryEvent } from '../types/history'
import { documentLoadTimes, documentReviewTimes } from './documentTiming'

export type DailyActivity = {
  date: string
  pending: number
  registered: number
  total: number
  partial: boolean
}

function localDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function dayLabel(date: Date): string {
  return [String(date.getFullYear()).padStart(4, '0'), String(date.getMonth() + 1).padStart(2, '0'), String(date.getDate()).padStart(2, '0')].join('-')
}

export function dailyDocumentActivity(events: HistoryEvent[], start: Date, end: Date, now: Date): DailyActivity[] {
  const valid = events.filter(event => Number.isFinite(Date.parse(event.fecha_evento))
    && Date.parse(event.fecha_evento) <= now.getTime())
  if (!valid.length || start >= end || start > now) return []
  const loaded = documentLoadTimes(valid, now)
  const reviewed = documentReviewTimes(valid, loaded, now)
  const registered = new Map<string, number>()
  let firstObserved = now.getTime()
  for (const event of valid) {
    const time = Date.parse(event.fecha_evento)
    firstObserved = Math.min(firstObserved, time)
    if (event.tipo_evento !== 'documento_registrado') continue
    const load = loaded.get(event.id_documento)
    if (load !== undefined && time < load) continue
    registered.set(event.id_documento, Math.min(registered.get(event.id_documento) ?? time, time))
  }
  // No se crean días anteriores al primer evento conocido ni días futuros.
  const cursor = localDay(new Date(Math.max(start.getTime(), firstObserved)))
  const rows: DailyActivity[] = []
  while (cursor < end && cursor <= now) {
    const next = new Date(cursor)
    next.setDate(next.getDate() + 1)
    const partial = next > now
    const beforeCut = (time: number) => partial ? time <= now.getTime() : time < next.getTime()
    let pending = 0
    for (const [id, time] of loaded) {
      const review = reviewed.get(id)
      const registration = registered.get(id)
      if (beforeCut(time) && (review === undefined || !beforeCut(review))
        && (registration === undefined || !beforeCut(registration))) pending++
    }
    const registrations = [...registered.values()].filter(time => time >= cursor.getTime() && beforeCut(time)).length
    rows.push({ date: dayLabel(cursor), pending, registered: registrations, total: pending + registrations, partial })
    cursor.setDate(cursor.getDate() + 1)
  }
  return rows
}
