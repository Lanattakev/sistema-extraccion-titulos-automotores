import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const compile = path => ts.transpileModule(read(path), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
}).outputText
const apiCode = ts.transpileModule(read('../src/services/api.ts'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 },
}).outputText
const { getHistory } = await import(`data:text/javascript;base64,${Buffer.from(apiCode).toString('base64')}`)
const nodeRequire = createRequire(import.meta.url)
const viewCode = compile('../src/views/HistoryView.tsx')
const hookCode = compile('../src/hooks/useHistory.ts')
const event = (id, type, date) => ({ id_evento: id, id_documento: 'doc-1', tipo_evento: type, fecha_evento: date, nombre_original: 'Título & original.pdf' })
const events = [
  event('event-3', 'documento_registrado', '2026-10-24T14:00:00+00:00'),
  event('event-2', 'documento_revisado', '2026-10-24T13:00:00+00:00'),
  event('event-1', 'documento_cargado', '2026-10-24T12:00:00+00:00'),
]

function render(state) {
  const module = { exports: {} }
  new Function('require', 'exports', viewCode)(name => {
    if (name === '../hooks/useHistory') return { useHistory: () => state }
    if (!name.startsWith('.')) return nodeRequire(name)
    const component = { exports: {} }
    new Function('require', 'exports', compile(`../src/views/${name}.tsx`))(nodeRequire, component.exports)
    return component.exports
  }, module.exports)
  return renderToStaticMarkup(createElement(module.exports.HistoryView))
}

function controller(getHistory) {
  const states = [], effects = []
  const react = {
    useState: initial => {
      const index = states.length
      states.push(initial)
      return [initial, value => { states[index] = typeof value === 'function' ? value(states[index]) : value }]
    },
    useRef: current => ({ current }), useCallback: callback => callback,
    useEffect: callback => { effects.push(callback) },
  }
  const module = { exports: {} }
  new Function('require', 'exports', hookCode)(name => name === 'react' ? react : { getHistory }, module.exports)
  return { hook: module.exports.useHistory(), states, effects }
}

test('GET history conserva eventos persistidos y un historial vacio sin inventar datos', async context => {
  const fetch = context.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/history')
    assert.equal(options, undefined)
    return Response.json(events)
  })
  assert.deepEqual(await getHistory(), events)
  fetch.mock.mockImplementation(async () => Response.json([]))
  assert.deepEqual(await getHistory(), [])
})

test('GET history muestra errores HTTP y de conexion reales', async context => {
  const fetch = context.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'Historial no disponible' }, { status: 503 }))
  await assert.rejects(getHistory(), /Historial no disponible/)
  fetch.mock.mockImplementation(async () => { throw new TypeError('offline') })
  await assert.rejects(getHistory(), /No se pudo conectar con el backend/)
})

test('GET history rechaza eventos malformados en lugar de mostrarlos como actividad real', async context => {
  const fetch = context.mock.method(globalThis, 'fetch', async () => Response.json(null))
  for (const body of [null, [{ ...events[0], fecha_evento: 'invalid' }], [{ ...events[0], tipo_evento: 'inventado' }], [{ ...events[0], id_documento: '' }]]) {
    fetch.mock.mockImplementation(async () => Response.json(body))
    await assert.rejects(getHistory(), /historial inválido/)
  }
})

test('Historial renderiza documento, accion, fechas y estados recibidos sin inventar operador', async context => {
  context.mock.method(globalThis, 'fetch', async () => Response.json(events))
  const saved = await getHistory()
  const html = render({ events: saved, loading: false, error: null, refresh: async () => {} })
  assert.match(html, /Título &amp; original.pdf/)
  for (const item of saved) {
    assert.ok(html.includes(item.id_evento))
    assert.ok(html.includes(item.fecha_evento))
  }
  assert.match(html, /Documento: doc-1/)
  assert.ok(html.indexOf('event-3') < html.indexOf('event-2'))
  assert.ok(html.indexOf('event-2') < html.indexOf('event-1'))
  for (const action of ['Documento cargado', 'Documento revisado', 'Documento registrado']) assert.ok(html.includes(action))
  for (const status of ['pending-review', 'reviewed', 'registered']) assert.ok(html.includes(`status-badge ${status}`))
  assert.doesNotMatch(html, /Operador|ejemplo|demostración|OP-00/)
})

test('Historial vacio muestra estado vacio sin filas ficticias', () => {
  const html = render({ events: [], loading: false, error: null, refresh: async () => {} })
  assert.match(html, /Todavía no hay eventos en el historial/)
  assert.doesNotMatch(html, /<li|<time|status-badge/)
})

test('Historial distingue un error real de un conjunto vacio y permite reintentar', () => {
  const html = render({ events: null, loading: false, error: 'Error real de consulta', refresh: async () => {} })
  assert.match(html, /role="alert"/)
  assert.match(html, /Error real de consulta/)
  assert.match(html, /Reintentar consulta/)
  assert.doesNotMatch(html, /Todavía no hay eventos|<li/)
})

test('Historial muestra carga sin adelantar estado vacio ni filas antiguas', () => {
  const html = render({ events, loading: true, error: null, refresh: async () => {} })
  assert.match(html, /Cargando historial/)
  assert.match(html, /role="status"/)
  assert.doesNotMatch(html, /Todavía no hay eventos|<li/)
})

test('hook carga al abrir y refresca mediante GET sin crear eventos', async context => {
  let requests = 0
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.ok(url.endsWith('/history'))
    assert.equal(options, undefined)
    requests++
    return Response.json(events)
  })
  const c = controller(getHistory)
  const cleanup = c.effects[0]()
  assert.equal(c.states[1], true)
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(c.states[0], events)
  assert.equal(requests, 1)
  await c.hook.refresh()
  assert.equal(requests, 2)
  assert.deepEqual(c.states[0], events)
  assert.equal(c.states[2], null)
  cleanup()
})

test('hook no permite que una respuesta antigua pise un refresco reciente', async () => {
  const finish = []
  const c = controller(() => new Promise(resolve => { finish.push(resolve) }))
  const first = c.hook.refresh(), second = c.hook.refresh()
  finish[1](events)
  await second
  finish[0]([])
  await first
  assert.deepEqual(c.states[0], events)
  assert.equal(c.states[1], false)
})

test('hook conserva error real y permite recuperar el historial tras reintentar', async () => {
  let fail = true
  const c = controller(async () => {
    if (fail) throw new Error('Consulta interrumpida')
    return events
  })
  await c.hook.refresh()
  assert.equal(c.states[0], null)
  assert.equal(c.states[2], 'Consulta interrumpida')
  fail = false
  await c.hook.refresh()
  assert.deepEqual(c.states[0], events)
  assert.equal(c.states[2], null)
})
