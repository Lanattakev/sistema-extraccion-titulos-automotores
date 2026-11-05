import type { PersistedDocument } from '../types/documents'
import type { VehicleIntake } from '../types/vehicles'
import type { HistoryEvent } from '../types/history'
import { documentLoadTimes, documentReviewTimes } from './documentTiming'

function isoWeekLabel(date: Date): string {
  // ISO: el jueves determina el año; la semana 01 contiene el 4 de enero.
  // Usar la fecha local en UTC evita que cambios de horario alteren el cálculo.
  const thursday = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
  thursday.setUTCDate(thursday.getUTCDate() + 4 - (thursday.getUTCDay() || 7))
  const year = thursday.getUTCFullYear()
  const firstThursday = new Date(Date.UTC(year, 0, 4))
  firstThursday.setUTCDate(firstThursday.getUTCDate() + 4 - (firstThursday.getUTCDay() || 7))
  const week = 1 + Math.round((thursday.getTime() - firstThursday.getTime()) / 604_800_000)
  return `${String(year).padStart(4, '0')}-${String(week).padStart(2, '0')}`
}

export function registrationPeriods(vehicles: VehicleIntake[], now: Date, unit: 'week' | 'month') {
  const count = unit === 'week' ? 6 : 3
  const current = new Date(now.getFullYear(), now.getMonth(), unit === 'week' ? now.getDate() : 1)
  if (unit === 'week') current.setDate(current.getDate() - (current.getDay() + 6) % 7)
  return Array.from({ length: count }, (_, index) => {
    const start = new Date(current)
    if (unit === 'week') start.setDate(start.getDate() - index * 7)
    else start.setMonth(start.getMonth() - index)
    const end = new Date(start)
    if (unit === 'week') end.setDate(end.getDate() + 7)
    else end.setMonth(end.getMonth() + 1)
    const label = unit === 'week'
      ? isoWeekLabel(start)
      : `${String(start.getFullYear()).padStart(4, '0')}-${String(start.getMonth() + 1).padStart(2, '0')}`
    const total = vehicles.filter(vehicle => {
      const date = Date.parse(vehicle.fecha_ingreso)
      return date >= start.getTime() && date < end.getTime() && date <= now.getTime()
    }).length
    return { start, end, label, count: total }
  })
}

export function documentRegistrationPeriods(documents: PersistedDocument[], events: HistoryEvent[], now: Date, unit: 'week' | 'month') {
  const loaded = documentLoadTimes(events, now)
  const unique = [...new Map(documents.map(document => [document.id_documento, document])).values()]
  return registrationPeriods([], now, unit).reverse().map(period => {
    const members = unique.filter(document => {
      const date = loaded.get(document.id_documento)
      return date !== undefined && date >= period.start.getTime() && date < period.end.getTime()
    })
    const registered = members.filter(document => document.estado === 'registrado').length
    const pending = members.length - registered
    return { start: period.start, end: period.end, isoLabel: period.label,
      label: unit === 'week' ? `Semana ${Number(period.label.slice(5))}` : period.label,
      registered, pending, total: registered + pending }
  })
}

export function documentTimeMetrics(documents: PersistedDocument[], events: HistoryEvent[], now: Date) {
  const loaded = documentLoadTimes(events, now)
  const reviewed = documentReviewTimes(events, loaded, now)
  const durations = [...reviewed].map(([id, time]) => time - loaded.get(id)!)
  const pendingAges = documents.filter(document => document.estado === 'pendiente')
    .flatMap(document => {
      const start = loaded.get(document.id_documento)
      return start === undefined ? [] : [now.getTime() - start]
    })
  const average = (values: number[]) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0
  return { reviewAverage: average(durations), reviewCount: durations.length,
    pendingAverage: average(pendingAges), pendingCount: pendingAges.length }
}

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
