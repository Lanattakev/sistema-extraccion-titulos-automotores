import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

// Renderiza los componentes reales en memoria con las dependencias ya instaladas.
const nodeRequire = createRequire(import.meta.url)
const modules = new Map()
function load(path) {
  if (modules.has(path)) return modules.get(path).exports
  const module = { exports: {} }
  modules.set(path, module)
  const { outputText } = ts.transpileModule(readFileSync(path, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
  })
  new Function('require', 'exports', outputText)(name => {
    if (!name.startsWith('.')) return nodeRequire(name)
    const base = resolve(dirname(path), name)
    return load(['.ts', '.tsx'].map(extension => base + extension).find(existsSync))
  }, module.exports)
  return module.exports
}
const { documentMetrics, topBrands } = load(fileURLToPath(new URL('../src/utils/metrics.ts', import.meta.url)))
const { MetricsView } = load(fileURLToPath(new URL('../src/views/MetricsView.tsx', import.meta.url)))
const fields = { patente: 'AB123CD', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M1', numero_chasis: 'C1', anio: 2020 }
const document = (id, estado) => ({ id_documento: id, nombre_original: `${id}.pdf`, ...fields, estado, id_interno: estado === 'registrado' ? `vehicle-${id}` : null })
const vehicle = (id, marca) => ({ vehicle: { ...fields, marca }, id_interno: id, archivo_origen: `${id}.pdf`, fecha_ingreso: '2026-10-24T12:00:00Z', requiere_revision: false })
function props(documents = [], vehicles = []) {
  return {
    documentState: { persistedDocuments: documents, documentsLoading: false, documentsError: null, refreshDocuments: async () => {} },
    vehicleState: { vehicles, loading: false, error: null, refresh: async () => {} },
  }
}
const render = state => renderToStaticMarkup(createElement(MetricsView, state))
function card(html, title) {
  const match = html.match(new RegExp(`<h2>${title}</h2><strong>(.*?)</strong>`))
  assert.ok(match, `Falta la tarjeta ${title}`)
  return match[1]
}

test('sin documentos los totales y el porcentaje son cero y finitos', () => {
  assert.deepEqual(documentMetrics([]), { total: 0, pendiente: 0, revisado: 0, registrado: 0, registeredPercentage: 0 })
  assert.deepEqual(topBrands([]), [])
})

test('distribucion y porcentaje se calculan desde los estados persistidos', () => {
  const documents = [document('a', 'pendiente'), document('b', 'revisado'), document('c', 'registrado'), document('d', 'registrado')]
  assert.deepEqual(documentMetrics(documents), { total: 4, pendiente: 1, revisado: 1, registrado: 2, registeredPercentage: 50 })
})

test('Top marcas agrupa espacios y mayusculas, ordena y limita a cinco marcas reales', () => {
  const vehicles = ['Toyota', ' TOYOTA ', 'toyota', 'Honda', 'honda', 'Ford', 'Audi', 'BMW', 'Renault'].map((brand, index) => vehicle(String(index), brand))
  assert.deepEqual(topBrands(vehicles), [
    { brand: 'TOYOTA', count: 3 }, { brand: 'HONDA', count: 2 },
    { brand: 'AUDI', count: 1 }, { brand: 'BMW', count: 1 }, { brand: 'FORD', count: 1 },
  ])
})

test('vista vacia muestra seis contadores en cero y dos estados vacios sin barras ficticias', () => {
  const html = render(props())
  for (const title of ['Vehículos registrados', 'Documentos totales', 'Pendientes de revisión', 'Revisados', 'Registrados']) assert.equal(card(html, title), '0')
  assert.equal(card(html, 'Porcentaje registrado'), '0%')
  assert.equal(html.split('Aún no hay datos suficientes para mostrar esta métrica.').length - 1, 2)
  assert.doesNotMatch(html, /role="meter"|NaN|Infinity|Ejemplo|ilustrativ|Actividad semanal/)
})

test('vista usa cantidades reales independientes de documentos y vehiculos sin hacer requests', context => {
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('Métricas no debe duplicar consultas') })
  const state = props([document('a', 'pendiente'), document('b', 'revisado'), document('c', 'registrado'), document('d', 'registrado')], [vehicle('1', 'Toyota'), vehicle('2', 'toyota'), vehicle('3', 'Honda')])
  const html = render(state)
  assert.equal(card(html, 'Vehículos registrados'), '3')
  assert.equal(card(html, 'Documentos totales'), '4')
  assert.equal(card(html, 'Pendientes de revisión'), '1')
  assert.equal(card(html, 'Revisados'), '1')
  assert.equal(card(html, 'Registrados'), '2')
  assert.equal(card(html, 'Porcentaje registrado'), '50%')
  assert.match(html, /aria-label="Vehículos TOYOTA" aria-valuenow="2"/)
  assert.match(html, /aria-label="Vehículos HONDA" aria-valuenow="1"/)
  assert.match(html, /aria-label="Pendiente" aria-valuenow="25"/)
  assert.match(html, /aria-label="Revisado" aria-valuenow="25"/)
  assert.match(html, /aria-label="Registrado" aria-valuenow="50"/)
  assert.equal(fetch.mock.callCount(), 0)
})

test('errores de consulta no se presentan como cero ni muestran graficos desactualizados', () => {
  const state = props([document('a', 'registrado')], [vehicle('1', 'Toyota')])
  state.documentState.documentsError = 'Error de documentos'
  state.vehicleState.error = 'Error de vehículos'
  const html = render(state)
  for (const title of ['Vehículos registrados', 'Documentos totales', 'Pendientes de revisión', 'Revisados', 'Registrados', 'Porcentaje registrado']) assert.equal(card(html, title), '—')
  assert.match(html, /Error de documentos/)
  assert.match(html, /Error de vehículos/)
  assert.doesNotMatch(html, /role="meter"|Aún no hay datos suficientes/)
})

test('carga inicial muestra progreso sin anunciar un conjunto vacio', () => {
  const state = props()
  state.documentState.documentsLoading = true
  state.vehicleState.loading = true
  const html = render(state)
  assert.equal(card(html, 'Documentos totales'), '—')
  assert.equal(card(html, 'Vehículos registrados'), '—')
  assert.match(html, /Actualizando documentos/)
  assert.match(html, /Actualizando vehículos/)
  assert.doesNotMatch(html, /role="meter"|Aún no hay datos suficientes|NaN|Infinity/)
})
