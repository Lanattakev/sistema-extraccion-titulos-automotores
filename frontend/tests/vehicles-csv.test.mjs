import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import * as React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const nodeRequire = createRequire(import.meta.url)
const compile = path => ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
}).outputText
function load(path, require = nodeRequire) {
  const module = { exports: {} }
  new Function('require', 'exports', compile(path))(require, module.exports)
  return module.exports
}
const numberUtils = load('../src/utils/registrationNumber.ts')
const csvUtils = load('../src/utils/vehiclesCsv.ts', name => name === './registrationNumber' ? numberUtils : nodeRequire(name))
const { vehiclesCsv, downloadVehiclesCsv } = csvUtils
const intake = {
  id_interno: 'registro-real-1', numero_registro: 1, vehicle: { patente: 'AB123CD', marca: 'Citroën', modelo: 'C4', numero_motor: 'M123', numero_chasis: 'C456', anio: 2020 },
  archivo_origen: 'Título.pdf', fecha_ingreso: '2026-10-24T12:00:00+00:00', requiere_revision: false,
}
const header = '"numero_registro","patente","marca","modelo","numero_motor","numero_chasis","anio","archivo_origen","fecha_ingreso","requiere_revision"\r\n'

function view(requireOverrides = {}) {
  return load('../src/views/VehiclesView.tsx', name => {
    if (name in requireOverrides) return requireOverrides[name]
    if (name === '../utils/registrationNumber') return numberUtils
    if (name === '../utils/vehiclesCsv') return csvUtils
    if (name.startsWith('../components/')) return load(`../src/views/${name}.tsx`)
    return nodeRequire(name)
  }).VehiclesView
}
const state = vehicles => ({ vehicles, loading: false, error: null, refresh: async () => {} })
function button(node, label) {
  if (!node || typeof node !== 'object') return undefined
  if (Array.isArray(node)) return node.map(child => button(child, label)).find(Boolean)
  if (node.type === 'button' && node.props.children === label) return node
  return button(node.props?.children, label)
}

test('numero visible usa al menos tres digitos sin truncar numeros mayores', () => {
  for (const [number, expected] of [[1, '001'], [2, '002'], [15, '015'], [999, '999'], [1000, '1000']]) {
    assert.equal(numberUtils.formatRegistrationNumber(number), expected)
    const csv = vehiclesCsv([{ ...intake, numero_registro: number }])
    assert.ok(csv.startsWith(`${header}"${expected}",`))
    assert.ok(!csv.includes(intake.id_interno))
  }
})

test('Vehiculos muestra el numero de registro en listado y ficha, conserva UUID como clave interna', () => {
  const VehiclesView = view()
  const html = renderToStaticMarkup(React.createElement(VehiclesView, { vehicleState: state([intake]) }))
  assert.match(html, /<td>001<\/td>/)
  assert.match(html, /N.º registro: 001/)
  assert.ok(!html.includes(intake.id_interno))
})

test('Inicio muestra numero de registro en registros recientes', () => {
  const { HomeView } = load('../src/views/HomeView.tsx', name => {
    if (name === '../utils/registrationNumber') return numberUtils
    if (name === '../components/UploadArea') return { UploadArea: () => null }
    if (name.startsWith('../components/')) return load(`../src/views/${name}.tsx`)
    return nodeRequire(name)
  })
  const html = renderToStaticMarkup(React.createElement(HomeView, {
    vehicleState: state([{ ...intake, numero_registro: 1000 }]), onFilesSelected: () => {},
  }))
  assert.match(html, /N.º registro/)
  assert.match(html, /<td>1000<\/td>/)
  assert.ok(!html.includes(intake.id_interno))
})

test('CSV incluye los diez encabezados y exactamente los vehiculos suministrados', () => {
  const second = { ...intake, id_interno: 'registro-real-2', numero_registro: 2, requiere_revision: true }
  const csv = vehiclesCsv([intake, second])
  assert.ok(csv.startsWith(header))
  assert.equal(csv, header
    + '"001","AB123CD","Citroën","C4","M123","C456","2020","Título.pdf","2026-10-24T12:00:00+00:00","false"\r\n'
    + '"002","AB123CD","Citroën","C4","M123","C456","2020","Título.pdf","2026-10-24T12:00:00+00:00","true"\r\n')
  assert.deepEqual(intake.vehicle, { patente: 'AB123CD', marca: 'Citroën', modelo: 'C4', numero_motor: 'M123', numero_chasis: 'C456', anio: 2020 })
})

test('CSV escapa comas, comillas, CRLF y saltos de linea preservando el valor original', () => {
  const special = {
    ...intake, id_interno: 'id,"1"',
    vehicle: { ...intake.vehicle, marca: 'Marca, S.A.', modelo: 'Modelo "Especial"\nsegunda línea', numero_motor: 'M\r123', numero_chasis: 'C\r\n456' },
    archivo_origen: 'Título, "original"\r\nfirmado.pdf',
  }
  assert.equal(vehiclesCsv([special]), header
    + '"001","AB123CD","Marca, S.A.","Modelo ""Especial""\nsegunda línea","M\r123","C\r\n456","2020","Título, ""original""\r\nfirmado.pdf","2026-10-24T12:00:00+00:00","false"\r\n')
})

test('sin vehiculos no se genera CSV ni se accede al navegador para descargar', context => {
  const createUrl = context.mock.method(URL, 'createObjectURL', () => { throw new Error('No debe crear un Blob descargable') })
  assert.equal(vehiclesCsv([]), null)
  assert.equal(downloadVehiclesCsv([]), false)
  assert.equal(createUrl.mock.callCount(), 0)
})

test('CSV conserva campos vacios del backend sin completarlos con datos de ejemplo', () => {
  const incomplete = {
    ...intake,
    vehicle: { ...intake.vehicle, marca: '', modelo: '', numero_motor: '', numero_chasis: '' },
    archivo_origen: '',
  }
  assert.equal(vehiclesCsv([incomplete]), header
    + '"001","AB123CD","","","","","2020","","2026-10-24T12:00:00+00:00","false"\r\n')
})

test('descarga usa Blob UTF-8, nombre fechado y libera los recursos del navegador', async context => {
  let blob
  const operations = []
  const link = { click: () => operations.push('click'), remove: () => operations.push('remove') }
  const original = Object.getOwnPropertyDescriptor(globalThis, 'document')
  Object.defineProperty(globalThis, 'document', { configurable: true, value: {
    createElement: tag => { assert.equal(tag, 'a'); return link },
    body: { appendChild: element => { assert.equal(element, link); operations.push('append') } },
  } })
  context.after(() => {
    if (original) Object.defineProperty(globalThis, 'document', original)
    else delete globalThis.document
  })
  context.mock.method(URL, 'createObjectURL', value => { blob = value; return 'blob:csv-download' })
  const revoke = context.mock.method(URL, 'revokeObjectURL', url => { assert.equal(url, 'blob:csv-download') })
  assert.equal(downloadVehiclesCsv([intake], new Date(2026, 0, 2)), true)
  assert.equal(link.download, 'vehiculos_2026-01-02.csv')
  assert.equal(link.href, 'blob:csv-download')
  assert.deepEqual(operations, ['append', 'click', 'remove'])
  assert.equal(blob.type, 'text/csv;charset=utf-8')
  const bytes = new Uint8Array(await blob.arrayBuffer())
  assert.deepEqual([...bytes.slice(0, 3)], [0xEF, 0xBB, 0xBF])
  assert.equal(new TextDecoder().decode(bytes), vehiclesCsv([intake]))
  await new Promise(resolve => setTimeout(resolve, 10))
  assert.equal(revoke.mock.callCount(), 1)
})

test('vista vacia explica que no hay vehiculos para exportar y deshabilita Exportar', () => {
  const VehiclesView = view()
  const html = renderToStaticMarkup(React.createElement(VehiclesView, { vehicleState: state([]) }))
  assert.match(html, /No hay vehículos para exportar/)
  assert.match(html, /<button[^>]*disabled=""[^>]*>Exportar CSV<\/button>/)
})

test('Exportar utiliza solo el listado real recibido sin requests ni fallback', context => {
  const supplied = [intake]
  const calls = []
  const fetch = context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe volver a consultar') })
  const VehiclesView = view({
    react: { ...React, useState: initial => [initial, () => {}] },
    '../utils/vehiclesCsv': { downloadVehiclesCsv: vehicles => calls.push(vehicles) },
  })
  const tree = VehiclesView({ vehicleState: state(supplied) })
  const exportButton = button(tree, 'Exportar CSV')
  assert.equal(exportButton.props.disabled, false)
  exportButton.props.onClick()
  assert.equal(calls.length, 1)
  assert.equal(calls[0], supplied)
  assert.equal(fetch.mock.callCount(), 0)
  assert.ok(button(tree, 'Actualizar'))
})

test('Exportar queda bloqueado en carga, error y lista vacia aunque se invoque el handler', () => {
  const calls = []
  const VehiclesView = view({
    react: { ...React, useState: initial => [initial, () => {}] },
    '../utils/vehiclesCsv': { downloadVehiclesCsv: vehicles => calls.push(vehicles) },
  })
  for (const vehicleState of [{ ...state([intake]), loading: true }, { ...state([intake]), error: 'Backend no disponible' }, state([]), state(null)]) {
    const exportButton = button(VehiclesView({ vehicleState }), 'Exportar CSV')
    assert.equal(exportButton.props.disabled, true)
    exportButton.props.onClick()
  }
  assert.equal(calls.length, 0)
})
