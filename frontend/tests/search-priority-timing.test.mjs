import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import * as React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const nodeRequire = createRequire(import.meta.url)
const sourcePath = path => fileURLToPath(new URL(`../src/${path}`, import.meta.url))
function loader(overrides = {}) {
  const cache = new Map()
  function load(path) {
    if (path.endsWith('.css')) return {}
    if (cache.has(path)) return cache.get(path).exports
    const module = { exports: {} }
    cache.set(path, module)
    const code = ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
    }).outputText
    new Function('require', 'exports', code)(name => {
      if (name in overrides) return overrides[name]
      if (!name.startsWith('.')) return nodeRequire(name)
      const base = resolve(dirname(path), name)
      return load([base, `${base}.ts`, `${base}.tsx`].find(existsSync))
    }, module.exports)
    return module.exports
  }
  return load
}
const load = loader()
const { searchVehicles } = load(sourcePath('utils/vehicleSearch.ts'))
const { documentLoadTimes, documentAge, documentReviewTimes, documentAging, documentAgingLabel, filterAndOrderDocuments, formatDuration, nextPriorityOrder } = load(sourcePath('utils/documentTiming.ts'))
const { dailyDocumentActivity } = load(sourcePath('utils/dailyActivity.ts'))
const { registrationPeriods, documentRegistrationPeriods, documentTimeMetrics } = load(sourcePath('utils/metrics.ts'))
const { registryRows, searchRegistryRows } = load(sourcePath('utils/registryRows.ts'))
const now = new Date(2027, 0, 6, 12)
const day = 86_400_000
const fields = { patente: 'LPY452', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M1', numero_chasis: 'C1', anio: 2020 }
const vehicle = (number, patente, date = now) => ({ numero_registro: number, id_interno: `uuid-${number}`, vehicle: { ...fields, patente }, fecha_ingreso: date.toISOString(), archivo_origen: 'titulo.pdf', requiere_revision: false })
const document = (id, estado = 'pendiente') => ({ id_documento: id, nombre_original: `${id}.pdf`, ...fields, estado, fallo: false, requiere_revision: estado !== 'registrado', id_interno: estado === 'registrado' ? `uuid-${id}` : null })
const event = (id, type, date, eventId = `${id}-${type}`) => ({ id_evento: eventId, id_documento: id, tipo_evento: type, nombre_original: `${id}.pdf`, fecha_evento: date instanceof Date ? date.toISOString() : date })
const state = vehicles => ({ vehicles, loading: false, error: null, refresh: async () => {} })
const history = events => ({ events, loading: false, error: null, refresh: async () => {} })

test('busqueda por numero exacto con ceros y patente sin distinguir mayusculas, sin marca/modelo', () => {
  const vehicles = [vehicle(1, 'LPY452'), vehicle(15, 'AB123CD'), vehicle(1000, 'XY987ZZ')]
  for (const query of ['001', '1', 'LPY452', 'lpy452', ' lPy452 ', 'lpy']) assert.deepEqual(searchVehicles(vehicles, query), [vehicles[0]])
  assert.deepEqual(searchVehicles(vehicles, '015'), [vehicles[1]])
  assert.deepEqual(searchVehicles(vehicles, '1000'), [vehicles[2]])
  assert.deepEqual(searchVehicles(vehicles, 'Toyota'), [])
  assert.deepEqual(searchVehicles(vehicles, 'Corolla'), [])
  assert.deepEqual(searchVehicles(vehicles, '15x'), [])
  assert.deepEqual(searchVehicles([], '001'), [])
  assert.equal(searchVehicles(vehicles, '  '), vehicles)
})

test('seis semanas de lunes a lunes incluyen semana actual, limites y cambio de año sin duplicados', () => {
  const vehicles = [vehicle(1, 'A', new Date(2026, 10, 30)), vehicle(2, 'B', new Date(2026, 11, 27, 23, 59, 59)),
    vehicle(3, 'C', new Date(2026, 11, 28)), vehicle(4, 'D', new Date(2027, 0, 4)),
    vehicle(5, 'E', new Date(2026, 10, 29, 23, 59)), vehicle(6, 'F', new Date(2027, 0, 7)),
    { ...vehicle(7, 'G'), fecha_ingreso: 'invalida' }]
  const periods = registrationPeriods(vehicles, now, 'week')
  assert.equal(periods.length, 6)
  assert.deepEqual(periods.map(period => period.count), [1, 1, 1, 0, 0, 1])
  assert.equal(periods[0].start.getTime(), new Date(2027, 0, 4).getTime())
  assert.equal(periods[5].start.getTime(), new Date(2026, 10, 30).getTime())
  assert.deepEqual(periods.map(period => period.label), ['2027-01', '2026-53', '2026-52', '2026-51', '2026-50', '2026-49'])
  for (let index = 0; index < periods.length - 1; index++) assert.equal(periods[index].start.getTime(), periods[index + 1].end.getTime())
  assert.equal(registrationPeriods([], new Date(2027, 0, 3, 23), 'week')[0].start.getTime(), new Date(2026, 11, 28).getTime())
})

test('tres meses calendario incluyen mes actual, cambio de año y febrero bisiesto', () => {
  const vehicles = [vehicle(1, 'A', new Date(2026, 10, 1)), vehicle(2, 'B', new Date(2026, 11, 1)), vehicle(3, 'C', new Date(2027, 0, 1)),
    vehicle(4, 'D', new Date(2026, 9, 31, 23, 59)), vehicle(5, 'E', new Date(2027, 0, 7))]
  const periods = registrationPeriods(vehicles, now, 'month')
  assert.deepEqual(periods.map(period => period.count), [1, 1, 1])
  assert.deepEqual(periods.map(period => period.start.getMonth()), [0, 11, 10])
  assert.deepEqual(periods.map(period => period.label), ['2027-01', '2026-12', '2026-11'])
  const leap = registrationPeriods([vehicle(1, 'A', new Date(2024, 1, 29, 23, 59)), vehicle(2, 'B', new Date(2024, 2, 1))], new Date(2024, 2, 1, 12), 'month')
  assert.deepEqual(leap.map(period => period.count), [1, 1, 0])
  assert.deepEqual(registrationPeriods([], now, 'month').map(period => period.count), [0, 0, 0])
})

test('etiquetas ISO YYYY-WW y meses YYYY-MM siguen el orden descendente solicitado', () => {
  const date = new Date(2026, 10, 4, 12)
  const weeks = registrationPeriods([], date, 'week')
  const months = registrationPeriods([], date, 'month')
  assert.deepEqual(weeks.map(period => period.label), ['2026-45', '2026-44', '2026-43', '2026-42', '2026-41', '2026-40'])
  assert.deepEqual(months.map(period => period.label), ['2026-11', '2026-10', '2026-09'])
  for (const periods of [weeks, months]) {
    for (const period of periods) assert.match(period.label, /^\d{4}-\d{2}$/)
    for (let index = 1; index < periods.length; index++) assert.ok(periods[index - 1].start > periods[index].start)
  }
})

test('año ISO puede ser anterior o posterior al año calendario y respeta lunes y domingo', () => {
  for (const [date, expected] of [
    [new Date(2021, 0, 1, 12), '2020-53'],
    [new Date(2021, 0, 3, 23, 59), '2020-53'],
    [new Date(2021, 0, 4), '2021-01'],
    [new Date(2018, 11, 31, 12), '2019-01'],
    [new Date(2026, 0, 1, 12), '2026-01'],
  ]) {
    const period = registrationPeriods([], date, 'week')[0]
    assert.equal(period.label, expected)
    assert.equal(period.start.getDay(), 1)
    assert.equal(period.end.getDay(), 1)
  }
})

test('tiempo de revision promedia primera revision valida por documento, no revisiones repetidas', () => {
  const start = new Date(now.getTime() - day)
  const events = [event('a', 'documento_revisado', new Date(start.getTime() + 4 * 3_600_000), 'late'),
    event('b', 'documento_revisado', new Date(start.getTime() + 4 * 3_600_000)),
    event('a', 'documento_revisado', new Date(start.getTime() + 2 * 3_600_000), 'first'),
    event('a', 'documento_cargado', start), event('b', 'documento_cargado', start),
    event('a', 'documento_cargado', new Date(start.getTime() + 1000), 'duplicate'),
    event('a', 'documento_revisado', new Date(start.getTime() - 1000), 'invalid'),
    event('missing', 'documento_revisado', start), event('a', 'documento_revisado', new Date(now.getTime() + day), 'future'),
    event('a', 'documento_revisado', 'invalida', 'bad')]
  const result = documentTimeMetrics([], events, now)
  assert.equal(result.reviewCount, 2)
  assert.equal(result.reviewAverage, 3 * 3_600_000)
})

test('antiguedad promedio usa solo documentos actualmente pendientes con carga real y no futura', () => {
  const documents = [document('a'), document('b'), document('reviewed', 'revisado'), document('registered', 'registrado'), document('missing'), document('future')]
  const events = [event('a', 'documento_cargado', new Date(now.getTime() - 2 * day)), event('b', 'documento_cargado', new Date(now.getTime() - 4 * day)),
    event('reviewed', 'documento_cargado', new Date(now.getTime() - 20 * day)), event('registered', 'documento_cargado', new Date(now.getTime() - 30 * day)),
    event('future', 'documento_cargado', new Date(now.getTime() + day))]
  assert.deepEqual(documentTimeMetrics(documents, events, now), { reviewAverage: 0, reviewCount: 0, pendingAverage: 3 * day, pendingCount: 2 })
  assert.deepEqual(documentTimeMetrics(documents, [], now), { reviewAverage: 0, reviewCount: 0, pendingAverage: 0, pendingCount: 0 })
  const loaded = documentLoadTimes(events, now)
  assert.equal(documentAge('a', loaded, now), 2 * day)
  assert.equal(documentAge('missing', loaded, now), null)
  assert.equal(documentAge('future', loaded, now), null)
})

test('formato de antiguedad usa minutos horas y dias sin inventar fechas faltantes', () => {
  for (const [duration, expected] of [[0, '0 min'], [25 * 60_000, '25 min'], [4 * 3_600_000, '4 h'], [day, '1 día'], [2 * day, '2 días'], [null, 'Sin fecha de carga']]) assert.equal(formatDuration(duration), expected)
})

test('aging aumenta solo para Pendientes y congela primera revision aun despues de registrar', () => {
  const start = new Date(now.getTime() - 3 * day)
  const firstReview = new Date(start.getTime() + 6 * 3_600_000)
  const events = [event('a', 'documento_cargado', start), event('a', 'documento_revisado', new Date(start.getTime() + day), 'second'),
    event('a', 'documento_revisado', firstReview, 'first'), event('a', 'documento_registrado', new Date(start.getTime() + 2 * day))]
  const loaded = documentLoadTimes(events, now)
  const reviewed = documentReviewTimes(events, loaded, now)
  const later = new Date(now.getTime() + day)
  assert.equal(documentAging('a', 'pendiente', loaded, reviewed, now), 3 * day)
  assert.equal(documentAging('a', 'pendiente', loaded, reviewed, later), 4 * day)
  for (const status of ['revisado', 'registrado']) {
    assert.equal(documentAgingLabel('a', status, loaded, reviewed, now), '6 h')
    assert.equal(documentAgingLabel('a', status, loaded, reviewed, later), '6 h')
  }
  assert.equal(formatDuration(2 * day + 4 * 3_600_000), '2 días 4 h')
  assert.equal(documentAgingLabel('missing', 'pendiente', loaded, reviewed, now), 'Sin fecha de carga')
  assert.equal(documentAgingLabel('a', 'registrado', loaded, new Map(), now), 'Sin fecha de revisión')
})

test('actividad diaria arrastra pendientes de dias previos y cuenta registros solo en su dia real', () => {
  const today = new Date(2027, 0, 6, 12)
  const events = [event('a', 'documento_cargado', new Date(2027, 0, 1, 10)),
    event('a', 'documento_revisado', new Date(2027, 0, 3, 14)),
    event('a', 'documento_registrado', new Date(2027, 0, 5, 9)),
    event('b', 'documento_cargado', new Date(2027, 0, 2, 10))]
  const daily = dailyDocumentActivity(events.reverse(), new Date(2027, 0, 1), new Date(2027, 0, 7), today)
  assert.deepEqual(daily.map(row => [row.date, row.pending, row.registered, row.total, row.partial]), [
    ['2027-01-01', 1, 0, 1, false], ['2027-01-02', 2, 0, 2, false],
    ['2027-01-03', 1, 0, 1, false], ['2027-01-04', 1, 0, 1, false],
    ['2027-01-05', 1, 1, 2, false], ['2027-01-06', 1, 0, 1, true],
  ])
  // La carga anterior a la ventana se conserva como pendiente en el corte.
  const window = dailyDocumentActivity(events, new Date(2027, 0, 4), new Date(2027, 0, 6), today)
  assert.deepEqual(window.map(row => [row.pending, row.registered]), [[1, 0], [1, 1]])
})

test('corte diario respeta medianoche local y hoy es parcial sin anticipar eventos futuros', () => {
  const midnight = new Date(2027, 0, 2)
  const events = [event('a', 'documento_cargado', new Date(2027, 0, 1, 23, 59)),
    event('a', 'documento_revisado', midnight), event('a', 'documento_registrado', new Date(2027, 0, 2, 12))]
  const atMidnight = dailyDocumentActivity(events, new Date(2027, 0, 1), new Date(2027, 0, 4), midnight)
  assert.deepEqual(atMidnight.map(row => [row.pending, row.registered, row.partial]), [[1, 0, false], [0, 0, true]])
  const atEnd = dailyDocumentActivity(events, new Date(2027, 0, 1), new Date(2027, 0, 4), new Date(2027, 0, 3))
  assert.deepEqual(atEnd.map(row => [row.pending, row.registered, row.partial]), [[1, 0, false], [0, 1, false], [0, 0, true]])
  const offset = dailyDocumentActivity([event('a', 'documento_cargado', new Date(2027, 0, 1, 23, 59).toISOString())], new Date(2027, 0, 1), new Date(2027, 0, 2), new Date(2027, 0, 3))
  assert.equal(offset[0].date, '2027-01-01')
  assert.equal(offset[0].pending, 1)
})

test('actividad diaria no inventa carga o revision ni duplica registros repetidos', () => {
  const events = [event('no-load', 'documento_registrado', new Date(2027, 0, 3, 10)),
    event('direct', 'documento_cargado', new Date(2027, 0, 3, 8)),
    event('direct', 'documento_registrado', new Date(2027, 0, 4, 10)),
    event('direct', 'documento_registrado', new Date(2027, 0, 4, 11), 'duplicate'),
    event('bad', 'documento_cargado', 'invalida'), event('future', 'documento_cargado', new Date(2027, 0, 8))]
  const rows = dailyDocumentActivity(events, new Date(2027, 0, 1), new Date(2027, 0, 6), now)
  assert.deepEqual(rows.map(row => [row.date, row.pending, row.registered]), [
    ['2027-01-03', 1, 1], ['2027-01-04', 0, 1], ['2027-01-05', 0, 0],
  ])
  assert.deepEqual(dailyDocumentActivity([], new Date(2027, 0, 1), new Date(2027, 0, 6), now), [])
  assert.deepEqual(dailyDocumentActivity(events, new Date(2026, 11, 1), new Date(2027, 0, 1), now), [])
  assert.deepEqual(dailyDocumentActivity(events, new Date(2027, 0, 7), new Date(2027, 0, 9), now), [])
})

test('actividad diaria cruza cambio de año y febrero bisiesto conservando formato de fecha', () => {
  const year = dailyDocumentActivity([event('a', 'documento_cargado', new Date(2026, 11, 31, 10))],
    new Date(2026, 11, 31), new Date(2027, 0, 3), new Date(2027, 0, 2, 12))
  assert.deepEqual(year.map(row => row.date), ['2026-12-31', '2027-01-01', '2027-01-02'])
  const leap = dailyDocumentActivity([event('a', 'documento_cargado', new Date(2024, 1, 28, 10))],
    new Date(2024, 1, 28), new Date(2024, 2, 2), new Date(2024, 2, 1, 12))
  assert.deepEqual(leap.map(row => row.date), ['2024-02-28', '2024-02-29', '2024-03-01'])
})

test('prioridad agrupa Pendientes Revisados Registrados antes de comparar antiguedad y se invierte', () => {
  const docs = [document('registered', 'registrado'), document('new'), document('review-old', 'revisado'), document('old'), document('review-new', 'revisado')]
  const loaded = documentLoadTimes([
    event('registered', 'documento_cargado', new Date(now.getTime() - 30 * day)),
    event('review-old', 'documento_cargado', new Date(now.getTime() - 20 * day)),
    event('review-new', 'documento_cargado', new Date(now.getTime() - 10 * day)),
    event('old', 'documento_cargado', new Date(now.getTime() - 2 * day)),
    event('new', 'documento_cargado', new Date(now.getTime() - day)),
  ], now)
  const ordered = filterAndOrderDocuments(docs, 'todos', 'oldest', loaded, {}, docs)
  assert.deepEqual(ordered.map(doc => doc.id_documento), ['old', 'new', 'review-old', 'review-new', 'registered'])
  assert.deepEqual(filterAndOrderDocuments(docs, 'todos', 'newest', loaded, {}, docs), [...ordered].reverse())
  assert.equal(docs[0].id_documento, 'registered')
  const confirmations = { old: { registered: { vehicle: fields, id_interno: 'uuid-old' } } }
  assert.deepEqual(filterAndOrderDocuments(docs, 'todos', 'oldest', loaded, confirmations, docs).map(doc => doc.id_documento),
    ['new', 'review-old', 'review-new', 'registered', 'old'])
})

test('filtros y prioridad ordenan antiguedad en ambos sentidos con faltantes al final sin mutar datos', () => {
  const docs = [document('new'), document('review', 'revisado'), document('old'), document('missing'), document('registered', 'registrado')]
  const original = [...docs]
  const loaded = documentLoadTimes([event('new', 'documento_cargado', new Date(now.getTime() - day)), event('old', 'documento_cargado', new Date(now.getTime() - 3 * day))], now)
  const ids = (filter, order) => filterAndOrderDocuments(docs, filter, order, loaded, {}, docs).map(doc => doc.id_documento)
  assert.deepEqual(ids('pendiente', 'oldest'), ['old', 'new', 'missing'])
  assert.deepEqual(ids('pendiente', 'newest'), ['new', 'old', 'missing'])
  assert.deepEqual(ids('revisado', 'oldest'), ['review'])
  assert.deepEqual(ids('registrado', 'oldest'), ['registered'])
  assert.equal(ids('todos', 'oldest').length, 5)
  assert.deepEqual(docs, original)
  const local = { old: { reviewed: fields }, new: { registered: { vehicle: fields, id_interno: 'uuid' } } }
  assert.deepEqual(filterAndOrderDocuments(docs, 'pendiente', 'oldest', loaded, local, docs).map(doc => doc.id_documento), ['missing'])
  const errors = [{ error: 'Fallo de extracción', fallo: true }]
  assert.deepEqual(filterAndOrderDocuments(errors, 'todos', 'oldest', loaded, {}, []), errors)
  assert.deepEqual(filterAndOrderDocuments(errors, 'pendiente', 'oldest', loaded, {}, []), [])
})

function walk(node, predicate) {
  if (!node || typeof node !== 'object') return []
  if (Array.isArray(node)) return node.flatMap(child => walk(child, predicate))
  return [...(predicate(node) ? [node] : []), ...walk(node.props?.children, predicate)]
}
function componentHarness(path, name, overrides = {}) {
  const slots = []
  let cursor = 0
  const react = { ...React, useState: initial => {
    const index = cursor++
    if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial
    return [slots[index], value => { slots[index] = typeof value === 'function' ? value(slots[index]) : value }]
  }, useEffect: () => {}, useRef: initial => {
    const index = cursor++
    if (!(index in slots)) slots[index] = { current: initial }
    return slots[index]
  } }
  const Component = loader({ ...overrides, react })(sourcePath(path))[name]
  return props => { cursor = 0; return Component(props) }
}

test('busqueda de la vista se actualiza al escribir y Exportar conserva todos los vehiculos cargados', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar') })
  const supplied = [vehicle(1, 'LPY452'), vehicle(2, 'AB123CD')]
  const calls = []
  const render = componentHarness('views/VehiclesView.tsx', 'VehiclesView', { '../utils/vehiclesCsv': { downloadVehiclesCsv: rows => calls.push(rows) } })
  const props = { vehicleState: state(supplied) }
  let tree = render(props)
  const search = walk(tree, node => node.props?.id === 'vehicle-search')[0]
  search.props.onChange({ target: { value: 'lpy452' } })
  tree = render(props)
  const plates = walk(tree, node => node.props?.className === 'plate')
  assert.deepEqual(plates.map(node => node.props.children), ['LPY452'])
  walk(tree, node => node.type === 'button' && node.props.children === 'Exportar CSV')[0].props.onClick()
  assert.equal(calls[0], supplied)
  walk(tree, node => node.props?.id === 'vehicle-search')[0].props.onChange({ target: { value: 'no-existe' } })
  tree = render(props)
  assert.equal(walk(tree, node => node.props?.className === 'plate').length, 0)
  assert.equal(walk(tree, node => node.type === 'p' && node.props.children === 'No hay registros que coincidan con la búsqueda y el estado.').length, 1)
  assert.equal(fetch.mock.callCount(), 0)
})

test('vista documental filtra estados, invierte flecha y restaura prioridad de Pendientes sin requests', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar') })
  const docs = [document('new'), document('review', 'revisado'), document('old'), document('registered', 'registrado'), document('missing')]
  const props = { now, historyState: history([event('old', 'documento_cargado', new Date(now.getTime() - 2 * day)), event('new', 'documento_cargado', new Date(now.getTime() - 25 * 60_000))]),
    persistedDocuments: docs, documentsLoading: false, documentsError: null, refreshDocuments: async () => {}, confirmations: { review: { reviewed: fields }, registered: { registered: { vehicle: fields, id_interno: 'uuid' } } }, batchConfirmation: null,
    onMarkReviewed: async () => {}, onInvalidateReview: () => {}, onConfirm: async () => {}, onConfirmSelected: async () => {} }
  const render = componentHarness('views/UploadView.tsx', 'UploadView')
  const results = tree => walk(tree, node => node.type?.name === 'BatchResult')
  const filter = (tree, value) => walk(tree, node => node.props?.id === 'document-status')[0].props.onChange({ target: { value } })
  const toggle = tree => {
    const header = walk(tree, node => node.type?.name === 'StateSortHeader')[0]
    return walk(header.type(header.props), node => node.type === 'button')[0]
  }
  let tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), docs.map(doc => doc.id_documento))
  assert.match(toggle(tree).props['aria-label'], /Estado ↕: orden normal/)
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['old', 'new', 'missing', 'review', 'registered'])
  assert.match(toggle(tree).props['aria-label'], /Estado ↑: mayor prioridad primero/)
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['registered', 'review', 'new', 'old', 'missing'])
  assert.match(toggle(tree).props['aria-label'], /Estado ↓: menor prioridad primero/)
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), docs.map(doc => doc.id_documento))
  toggle(tree).props.onClick()
  tree = render(props)
  filter(tree, 'pendiente')
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['old', 'new', 'missing'])
  assert.deepEqual(results(tree).map(node => node.props.ageLabel), ['2 días', '25 min', 'Sin fecha de carga'])
  assert.match(toggle(tree).props['aria-label'], /mayor prioridad primero/)
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['new', 'old', 'missing'])
  assert.match(toggle(tree).props['aria-label'], /menor prioridad primero/)
  filter(tree, 'revisado')
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['review'])
  filter(tree, 'registrado')
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['registered'])
  filter(tree, 'pendiente')
  tree = render(props)
  assert.deepEqual(results(tree).map(node => node.props.result.id_documento), ['new', 'old', 'missing'])
  filter(tree, 'todos')
  assert.equal(results(render(props)).length, 5)
  assert.equal(fetch.mock.callCount(), 0)
})

test('metricas renderizan periodos y promedios reales; errores de historial no simulan ceros', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar') })
  const { MetricsView } = load(sourcePath('views/MetricsView.tsx'))
  const props = { now, vehicleState: state([vehicle(1, 'LPY452')]), documentState: { persistedDocuments: [document('pending')], documentsLoading: false, documentsError: null, refreshDocuments: async () => {} },
    historyState: history([event('pending', 'documento_cargado', new Date(now.getTime() - 2 * day)), event('review', 'documento_cargado', new Date(now.getTime() - day)), event('review', 'documento_revisado', new Date(now.getTime() - day + 4 * 3_600_000))]) }
  let html = renderToStaticMarkup(React.createElement(MetricsView, props))
  assert.match(html, /Tiempo promedio de revisión<\/h2><strong>4 h/)
  assert.match(html, /Antigüedad promedio de pendientes<\/h2><strong>2 días/)
  assert.match(html, /Registros de las últimas 6 semanas/)
  assert.match(html, /Registros de los últimos 3 meses/)
  html = renderToStaticMarkup(React.createElement(MetricsView, { ...props, historyState: { ...props.historyState, error: 'Historial no disponible' } }))
  assert.match(html, /Tiempo promedio de revisión<\/h2><strong>—/)
  assert.match(html, /Antigüedad promedio de pendientes<\/h2><strong>—/)
  assert.equal(fetch.mock.callCount(), 0)
})

test('tabla documental muestra Tiempo / Aging vivo en Pendientes y congelado en Revisados y Registrados sin requests', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar para actualizar aging') })
  const { UploadView } = load(sourcePath('views/UploadView.tsx'))
  const docs = [document('pending'), document('review', 'revisado'), document('registered', 'registrado')]
  const events = [event('pending', 'documento_cargado', new Date(now.getTime() - 35 * 60_000)),
    event('review', 'documento_cargado', new Date(now.getTime() - 3 * day)),
    event('review', 'documento_revisado', new Date(now.getTime() - 3 * day + 6 * 3_600_000)),
    event('registered', 'documento_cargado', new Date(now.getTime() - 5 * day)),
    event('registered', 'documento_revisado', new Date(now.getTime() - 3 * day + 4 * 3_600_000))]
  const props = { now, historyState: history(events), persistedDocuments: docs, documentsLoading: false, documentsError: null,
    refreshDocuments: async () => {}, confirmations: { review: { reviewed: fields }, registered: { registered: { vehicle: fields, id_interno: 'uuid' } } }, batchConfirmation: null,
    onMarkReviewed: async () => {}, onInvalidateReview: () => {}, onConfirm: async () => {}, onConfirmSelected: async () => {} }
  const aging = html => [...html.matchAll(/class="document-aging"><strong>([^<]*)/g)].map(match => match[1])
  let html = renderToStaticMarkup(React.createElement(UploadView, props))
  assert.match(html, /<th scope="col">Tiempo \/ Aging<\/th>/)
  assert.deepEqual(aging(html), ['35 min', '6 h', '2 días 4 h'])
  assert.match(html, /Seleccionar pending.pdf/)
  assert.match(html, /Ver detalle de pending.pdf/)
  html = renderToStaticMarkup(React.createElement(UploadView, { ...props, now: new Date(now.getTime() + day) }))
  assert.deepEqual(aging(html), ['1 día', '6 h', '2 días 4 h'])
  assert.equal(fetch.mock.callCount(), 0)
})

test('barras CSS muestran ambas series, valores y totales reales; ceros sin barras falsas y vacio sin historial', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar') })
  const { DailyActivityChart } = load(sourcePath('components/DailyActivityChart.tsx'))
  const props = { start: new Date(2027, 0, 1), end: new Date(2027, 0, 4), now: new Date(2027, 0, 3, 12), label: '2027-01',
    events: [event('a', 'documento_cargado', new Date(2027, 0, 1, 10)), event('a', 'documento_registrado', new Date(2027, 0, 2, 10))] }
  let html = renderToStaticMarkup(React.createElement(DailyActivityChart, props))
  assert.match(html, /2027-01-01: 1 pendientes, 0 registrados, total de la barra 1, al cierre/)
  assert.match(html, /2027-01-02: 0 pendientes, 1 registrados, total de la barra 1, al cierre/)
  assert.match(html, /2027-01-03: 0 pendientes, 0 registrados, total de la barra 0, hasta ahora/)
  assert.match(html, /class="daily-pending" style="width:100%"/)
  assert.match(html, /class="daily-registered" style="width:100%"/)
  assert.match(html, /class="daily-pending" style="width:0%"/)
  assert.match(html, /Pendientes al último corte: <strong>0<\/strong>/)
  assert.match(html, /Registrados en el período: <strong>1<\/strong>/)
  assert.doesNotMatch(html, /NaN|Infinity/)
  html = renderToStaticMarkup(React.createElement(DailyActivityChart, { ...props, events: [] }))
  assert.match(html, /No hay historial suficiente/)
  assert.doesNotMatch(html, /daily-stack|role="img"/)
  assert.equal(fetch.mock.callCount(), 0)
})

test('metricas muestra barras semanales y mensuales de antiguo a actual aun si falla vehiculos', () => {
  const { MetricsView } = load(sourcePath('views/MetricsView.tsx'))
  const props = { now, vehicleState: { ...state([]), error: 'Sin vehículos' },
    documentState: { persistedDocuments: [document('a')], documentsLoading: false, documentsError: null, refreshDocuments: async () => {} },
    historyState: history([event('a', 'documento_cargado', new Date(2027, 0, 4, 10))]) }
  const html = renderToStaticMarkup(React.createElement(MetricsView, props))
  assert.match(html, /Semana 1 \(2027-01\): 0 registrados, 1 pendientes de registro, total 1/)
  const periods = [...html.matchAll(/class="period-label" title="([^"]+)">([^<]+)<small>/g)]
  assert.deepEqual(periods.map(match => match[1]), ['2026-49', '2026-50', '2026-51', '2026-52', '2026-53', '2027-01', '2026-11', '2026-12', '2027-01'])
  assert.deepEqual(periods.slice(0, 6).map(match => match[2]), ['Semana 49', 'Semana 50', 'Semana 51', 'Semana 52', 'Semana 53', 'Semana 1'])
  const failed = renderToStaticMarkup(React.createElement(MetricsView, { ...props, historyState: { ...props.historyState, error: 'Historial inaccesible' } }))
  assert.doesNotMatch(failed, /class="period-stack"/)
  assert.match(failed, /La actividad por período estará disponible al recuperar documentos e historial/)
})

test('control Estado recorre normal ↕ mayor ↑ menor ↓ y vuelve a normal con aria-sort', () => {
  const { StateSortHeader } = load(sourcePath('components/StateSortHeader.tsx'))
  let order = 'normal'
  for (const [symbol, ariaSort] of [['↕', 'none'], ['↑', 'ascending'], ['↓', 'descending'], ['↕', 'none']]) {
    const tree = StateSortHeader({ order, onChange: next => { order = next } })
    assert.equal(tree.props['aria-sort'], ariaSort)
    const control = walk(tree, node => node.type === 'button')[0]
    assert.ok(control.props['aria-label'].startsWith(`Estado ${symbol}:`))
    control.props.onClick()
  }
  assert.equal(nextPriorityOrder('low'), 'normal')
})

test('registros combina documentos y vehiculos sin duplicar ni asignar numero a pendientes', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar') })
  const vehicles = [vehicle(1, 'REG111'), vehicle(2, 'EXT222')]
  const docs = [{ ...document('registered', 'registrado'), id_interno: 'uuid-1', patente: 'REG111' },
    { ...document('new'), patente: 'NEW111' }, { ...document('review', 'revisado'), patente: 'REV111' }, { ...document('old'), patente: 'OLD111' }]
  const rows = registryRows(docs, vehicles)
  assert.equal(rows.length, 5)
  assert.equal(rows.filter(row => row.intake?.id_interno === 'uuid-1').length, 1)
  assert.equal(rows.find(row => row.document?.id_documento === 'old').intake, undefined)
  assert.equal(searchRegistryRows(rows, '001')[0].document.id_documento, 'registered')
  assert.equal(searchRegistryRows(rows, 'old111')[0].document.id_documento, 'old')
  const exported = []
  const render = componentHarness('views/VehiclesView.tsx', 'VehiclesView', { '../utils/vehiclesCsv': { downloadVehiclesCsv: values => exported.push(values) } })
  const props = { now, vehicleState: state(vehicles), historyState: history([
    event('old', 'documento_cargado', new Date(now.getTime() - 4 * day)),
    event('new', 'documento_cargado', new Date(now.getTime() - day)),
    event('registered', 'documento_cargado', new Date(now.getTime() - 10 * day)),
  ]), documentState: { persistedDocuments: docs, documentsLoading: false, documentsError: null, refreshDocuments: async () => {} } }
  const plates = tree => walk(tree, node => node.props?.className === 'plate').map(node => node.props.children)
  const toggle = tree => { const header = walk(tree, node => node.type?.name === 'StateSortHeader')[0]; return walk(header.type(header.props), node => node.type === 'button')[0] }
  let tree = render(props)
  assert.deepEqual(plates(tree), ['REG111', 'NEW111', 'REV111', 'OLD111', 'EXT222'])
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(plates(tree), ['OLD111', 'NEW111', 'REV111', 'REG111', 'EXT222'])
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(plates(tree), ['REG111', 'EXT222', 'REV111', 'NEW111', 'OLD111'])
  toggle(tree).props.onClick()
  tree = render(props)
  assert.deepEqual(plates(tree), ['REG111', 'NEW111', 'REV111', 'OLD111', 'EXT222'])
  walk(tree, node => node.props?.id === 'vehicle-search')[0].props.onChange({ target: { value: '001' } })
  tree = render(props)
  assert.deepEqual(plates(tree), ['REG111'])
  walk(tree, node => node.type === 'button' && node.props.children === 'Exportar CSV')[0].props.onClick()
  assert.equal(exported[0], vehicles)
  walk(tree, node => node.props?.id === 'vehicle-search')[0].props.onChange({ target: { value: 'old111' } })
  tree = render({ ...props, vehicleState: state([]) })
  assert.deepEqual(plates(tree), ['OLD111'])
  assert.equal(walk(tree, node => node.type === 'button' && node.props.children === 'Exportar CSV')[0].props.disabled, true)
  assert.equal(fetch.mock.callCount(), 0)
})

test('barras por periodo incluyen Revisados como pendientes y total coincide con ambas series', () => {
  const date = new Date(2026, 10, 4, 12)
  const docs = [document('sep', 'registrado'), document('w40'), document('w41', 'revisado'), document('w42', 'registrado'), document('w43'), document('w44', 'revisado'), document('w45', 'registrado'), document('missing')]
  const events = [event('sep', 'documento_cargado', new Date(2026, 8, 2)),
    ...[1, 5, 12, 19, 26].map((day, index) => event(`w${40 + index}`, 'documento_cargado', new Date(2026, 9, day))),
    event('w45', 'documento_cargado', new Date(2026, 10, 2)),
    event('future', 'documento_cargado', new Date(2026, 10, 5))]
  const weeks = documentRegistrationPeriods([...docs, docs[0]], events, date, 'week')
  const months = documentRegistrationPeriods(docs, events, date, 'month')
  assert.deepEqual(weeks.map(period => period.label), ['Semana 40', 'Semana 41', 'Semana 42', 'Semana 43', 'Semana 44', 'Semana 45'])
  assert.deepEqual(weeks.map(period => [period.registered, period.pending]), [[0, 1], [0, 1], [1, 0], [0, 1], [0, 1], [1, 0]])
  assert.deepEqual(months.map(period => period.label), ['2026-09', '2026-10', '2026-11'])
  assert.deepEqual(months.map(period => [period.registered, period.pending, period.total]), [[1, 0, 1], [1, 4, 5], [1, 0, 1]])
  for (const period of [...weeks, ...months]) assert.equal(period.total, period.registered + period.pending)
  const { PeriodActivityChart } = load(sourcePath('components/PeriodActivityChart.tsx'))
  const html = renderToStaticMarkup(React.createElement(PeriodActivityChart, { periods: months, label: 'Meses' }))
  assert.match(html, /2026-10 \(2026-10\): 1 registrados, 4 pendientes de registro, total 5/)
  assert.match(html, /class="period-registered" style="width:20%"/)
  assert.match(html, /class="period-pending" style="width:80%"/)
  assert.match(html, /3 registrados \/ 4 pendientes de registro · Total 7/)
  const css = readFileSync(sourcePath('App.css'), 'utf8')
  assert.match(css, /\.period-stack\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*row;/)
  assert.match(css, /\.period-registered\s*\{\s*background:\s*#3274c7;/)
  assert.match(css, /\.period-pending\s*\{\s*background:\s*#e3b93f;/)
})

test('App comparte un unico historial entre documentos metricas e historial, sin consultas desde las vistas', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe duplicar consultas') })
  const shared = history([])
  let page = 'metrics'
  let historyCalls = 0
  const react = { ...React, useState: initial => [initial === 'home' ? page : typeof initial === 'function' ? initial() : initial, () => {}],
    useRef: current => ({ current }), useEffect: () => {}, useCallback: callback => callback }
  const { default: App } = loader({ react,
    './hooks/useHistory': { useHistory: () => { historyCalls++; return shared } },
    './hooks/useVehicles': { useVehicles: () => state([]) },
    './hooks/useDocumentConfirmation': { useDocumentConfirmation: () => ({ persistedDocuments: [], documentsLoading: false, documentsError: null }) },
  })(sourcePath('App.tsx'))
  for (const [selected, name] of [['metrics', 'MetricsView'], ['upload', 'UploadView'], ['history', 'HistoryView']]) {
    page = selected
    const before = historyCalls
    const tree = App()
    assert.equal(historyCalls, before + 1)
    const view = walk(tree, node => node.type?.name === name)[0]
    assert.ok(view)
    assert.equal(view.props.historyState.events, shared.events)
    assert.equal(view.props.historyState.loading, shared.loading)
  }
  assert.equal(fetch.mock.callCount(), 0)
})
