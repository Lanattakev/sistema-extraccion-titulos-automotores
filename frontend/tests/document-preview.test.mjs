import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import * as React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import ts from 'typescript'

const nodeRequire = createRequire(import.meta.url)
function loader(overrides = {}) {
  const cache = new Map()
  return function load(path) {
    const url = path instanceof URL ? path : new URL(path, import.meta.url)
    if (cache.has(url.href)) return cache.get(url.href)
    const module = { exports: {} }
    cache.set(url.href, module.exports)
    const code = ts.transpileModule(readFileSync(url, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023, jsx: ts.JsxEmit.ReactJSX },
    }).outputText
    new Function('require', 'exports', code)(name => {
      if (name in overrides) return overrides[name]
      if (!name.startsWith('.')) return nodeRequire(name)
      const base = new URL(name, url)
      return load(['.ts', '.tsx'].map(extension => new URL(base.href + extension)).find(existsSync))
    }, module.exports)
    return module.exports
  }
}
const load = loader()
const { DocumentReview } = load('../src/components/DocumentReview.tsx')
const { DocumentPreview } = load('../src/components/DocumentPreview.tsx')
const { documentContentUrl } = load('../src/services/api.ts')
const fields = { patente: 'AB123CD', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M123', numero_chasis: 'C456', anio: 2020 }
const result = { id_documento: 'doc-1', nombre_original: 'Título.PDF', ...fields, fallo: false }
const properties = overrides => ({
  result, confirmations: {}, batchConfirmation: null,
  onMarkReviewed: async () => {}, onInvalidateReview: () => {}, onConfirm: async () => {},
  onClose: () => {}, onDraftChange: () => {}, ...overrides,
})
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props))
function walk(node, predicate) {
  if (!node || typeof node !== 'object') return []
  if (Array.isArray(node)) return node.flatMap(child => walk(child, predicate))
  return [...(predicate(node) ? [node] : []), ...walk(node.props?.children, predicate)]
}
const button = (tree, text) => walk(tree, node => node.type === 'button' && node.props.children === text)[0]
function harness(component) {
  const slots = []
  let cursor = 0
  const hooks = { ...React,
    useId: () => 'review-test',
    useState: initial => {
      const index = cursor++
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial
      return [slots[index], value => { slots[index] = typeof value === 'function' ? value(slots[index]) : value }]
    },
    useRef: initial => {
      const index = cursor++
      if (!(index in slots)) slots[index] = { current: initial }
      return slots[index]
    },
  }
  const Component = loader({ react: hooks })(`../src/components/${component}.tsx`)[component]
  return props => { cursor = 0; return Component(props) }
}
function key(overrides = {}) {
  return { key: 'Enter', ctrlKey: true, altKey: false, metaKey: false, shiftKey: false,
    defaultPrevented: false, repeat: false, nativeEvent: { isComposing: false },
    preventDefault() { this.defaultPrevented = true }, ...overrides }
}

test('URL canónica codifica el ID como un único segmento y no consulta ni usa archivos locales', context => {
  context.mock.method(globalThis, 'fetch', () => { throw new Error('No debe consultar desde la URL') })
  assert.equal(documentContentUrl('a/b ?#'), 'http://127.0.0.1:8000/api/v1/documents/a%2Fb%20%3F%23/content')
})

test('revisión muestra el original PDF junto al formulario con seis campos etiquetados y atajos accesibles', () => {
  const html = render(DocumentReview, properties())
  assert.match(html, /class="document-review-layout"/)
  assert.ok(html.indexOf('<iframe') < html.indexOf('<form'))
  assert.match(html, /<iframe[^>]*src="http:\/\/127\.0\.0\.1:8000\/api\/v1\/documents\/doc-1\/content"/)
  assert.match(html, /title="Documento original: Título.PDF"/)
  assert.match(html, /Abrir original en otra pestaña/)
  assert.equal((html.match(/<input/g) ?? []).length, 6)
  for (const [field] of Object.entries(fields)) {
    const input = html.match(new RegExp(`<input[^>]*id="([^"]+)"[^>]*name="${field}"`))
    assert.ok(input, field)
    assert.ok(html.includes(`for="${input[1]}"`))
  }
  assert.match(html, /aria-describedby=/)
  assert.match(html, /aria-keyshortcuts="Control\+Enter"/)
  assert.match(html, /aria-keyshortcuts="Escape"/)
  assert.doesNotMatch(html, /blob:|file:/)
})

for (const extension of ['png', 'JPG', 'jpeg']) {
  test(`visor de ${extension} usa imagen con texto alternativo, zoom y región desplazable por teclado`, () => {
    const html = render(DocumentPreview, { documentId: 'persisted-id', name: `Título.${extension}` })
    assert.match(html, /<img[^>]*alt="Documento original: Título\./)
    assert.match(html, /role="region"[^>]*aria-label="Vista del documento original"[^>]*tabindex="0"/)
    assert.match(html, /aria-label="Zoom de la imagen"/)
    assert.match(html, /Acercar imagen/)
    assert.match(html, /Alejar imagen/)
    assert.doesNotMatch(html, /<iframe/)
  })
}

test('nombre desconocido y resultado sin ID no fabrican una vista previa ni una URL inválida', () => {
  const html = render(DocumentPreview, { documentId: 'doc-1', name: '<script>.txt' })
  assert.doesNotMatch(html, /<img|<iframe|<script>/)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /formato no admite/)
  const missing = render(DocumentReview, properties({ result: { ...result, id_documento: null } }))
  assert.match(missing, /No hay un original disponible/)
  assert.doesNotMatch(missing, /\/documents\/(null|undefined)\/content/)
})

test('zoom de imagen modifica tamaño, respeta límites y permite restablecer sin perder el original', () => {
  const view = harness('DocumentPreview')
  const props = { documentId: 'doc-1', name: 'foto.png' }
  let tree = view(props)
  assert.equal(button(tree, 'Restablecer zoom').props.disabled, true)
  button(tree, 'Acercar imagen').props.onClick()
  tree = view(props)
  assert.equal(walk(tree, node => node.type === 'img')[0].props.style.width, '125%')
  for (let i = 0; i < 20; i++) button(view(props), 'Acercar imagen').props.onClick()
  assert.equal(button(view(props), 'Acercar imagen').props.disabled, true)
  assert.equal(walk(view(props), node => node.type === 'img')[0].props.style.width, '250%')
  for (let i = 0; i < 20; i++) button(view(props), 'Alejar imagen').props.onClick()
  assert.equal(button(view(props), 'Alejar imagen').props.disabled, true)
  button(view(props), 'Restablecer zoom').props.onClick()
  tree = view(props)
  const image = walk(tree, node => node.type === 'img')[0]
  assert.equal(image.props.style.width, '100%')
  assert.equal(image.props.src, documentContentUrl('doc-1'))
})

test('fallo de carga conserva enlace seguro al original y permite reintentar la vista previa', () => {
  const view = harness('DocumentPreview')
  const props = { documentId: 'doc-1', name: 'foto.png' }
  walk(view(props), node => node.type === 'img')[0].props.onError()
  const failed = view(props)
  assert.equal(walk(failed, node => node.props?.role === 'alert').length, 1)
  assert.equal(walk(failed, node => node.type === 'img').length, 0)
  const link = walk(failed, node => node.type === 'a')[0]
  assert.equal(link.props.href, documentContentUrl('doc-1'))
  assert.equal(link.props.rel, 'noopener noreferrer')
  button(failed, 'Reintentar vista previa').props.onClick()
  assert.equal(walk(view(props), node => node.type === 'img').length, 1)
})

test('Ctrl+Enter y botón comparten bloqueo sincrónico y no duplican una confirmación pendiente', async () => {
  const view = harness('DocumentReview')
  const calls = []
  let finish
  const props = properties({ confirmations: { 'doc-1': { reviewed: fields } }, onConfirm: id => {
    calls.push(id)
    return new Promise(resolve => { finish = resolve })
  } })
  const tree = view(props)
  const event = key()
  tree.props.onKeyDown(event)
  button(tree, 'Confirmar y registrar').props.onClick()
  tree.props.onKeyDown(key())
  assert.equal(event.defaultPrevented, true)
  assert.deepEqual(calls, ['doc-1'])
  finish()
  await new Promise(resolve => setImmediate(resolve))
  view({ ...props, confirmations: { 'doc-1': { reviewed: fields, registered: { vehicle: fields, id_interno: 'v1' } } } }).props.onKeyDown(key())
  assert.deepEqual(calls, ['doc-1'])
})

for (const [label, overrides] of [
  ['pendiente sin revisión', {}],
  ['revisión invalidada', { confirmations: { 'doc-1': { reviewed: fields, dirty: true } } }],
  ['operación en curso', { confirmations: { 'doc-1': { reviewed: fields, pending: true } } }],
  ['ya registrado', { confirmations: { 'doc-1': { reviewed: fields, registered: { vehicle: fields, id_interno: 'v1' } } } }],
  ['lote en curso', { confirmations: { 'doc-1': { reviewed: fields } }, batchConfirmation: { running: true } }],
  ['sin ID', { result: { ...result, id_documento: null } }],
]) {
  test(`atajo no confirma ni guarda revisiones automáticamente: ${label}`, () => {
    const view = harness('DocumentReview')
    let calls = 0
    view(properties({ ...overrides, onConfirm: async () => { calls++ }, onMarkReviewed: async () => { calls++ } })).props.onKeyDown(key())
    assert.equal(calls, 0)
  })
}

test('Escape y botón cierran la revisión libre pero respetan los bloqueos de operaciones', () => {
  const view = harness('DocumentReview')
  let closed = 0
  const props = properties({ onClose: () => { closed++ } })
  view(props).props.onKeyDown(key({ key: 'Escape', ctrlKey: false }))
  button(view(props), 'Cerrar revisión').props.onClick()
  assert.equal(closed, 2)
  for (const changes of [{ confirmations: { 'doc-1': { pending: true } } }, { batchConfirmation: { running: true } }]) {
    const tree = view({ ...props, ...changes })
    tree.props.onKeyDown(key({ key: 'Escape', ctrlKey: false }))
    assert.equal(button(tree, 'Cerrar revisión').props.disabled, true)
  }
  assert.equal(closed, 2)
})

test('Enter normal, repetición, composición IME y eventos consumidos no activan confirmaciones', () => {
  const view = harness('DocumentReview')
  let calls = 0
  const tree = view(properties({ confirmations: { 'doc-1': { reviewed: fields } }, onConfirm: async () => { calls++ } }))
  for (const event of [key({ ctrlKey: false }), key({ repeat: true }), key({ nativeEvent: { isComposing: true } }), key({ defaultPrevented: true }), key({ altKey: true })]) tree.props.onKeyDown(event)
  assert.equal(calls, 0)
})

test('formulario conserva correcciones, valida año y guarda revisión sin registrar automáticamente', async () => {
  const view = harness('DocumentReview')
  const saved = [], drafts = [], invalidated = []
  const props = properties({ onMarkReviewed: async (id, values) => saved.push([id, values]), onDraftChange: values => drafts.push(values), onInvalidateReview: id => invalidated.push(id) })
  walk(view(props), node => node.type === 'input' && node.props.name === 'modelo')[0].props.onChange({ target: { value: 'Corolla corregido' } })
  walk(view(props), node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
  assert.deepEqual(saved, [['doc-1', { ...fields, modelo: 'Corolla corregido' }]])
  assert.equal(drafts[0].modelo, 'Corolla corregido')
  assert.deepEqual(invalidated, ['doc-1'])
  walk(view(props), node => node.type === 'input' && node.props.name === 'anio')[0].props.onChange({ target: { value: '0' } })
  walk(view(props), node => node.type === 'form')[0].props.onSubmit({ preventDefault() {} })
  assert.equal(saved.length, 1)
  assert.equal(walk(view(props), node => node.props?.role === 'alert').length, 1)
})

test('error inesperado de confirmación se comunica y libera el bloqueo para reintentar', async () => {
  const view = harness('DocumentReview')
  let calls = 0
  const props = properties({ confirmations: { 'doc-1': { reviewed: fields } }, onConfirm: async () => { calls++; throw new Error('Conexión interrumpida') } })
  view(props).props.onKeyDown(key())
  await new Promise(resolve => setImmediate(resolve))
  assert.match(walk(view(props), node => node.props?.role === 'alert')[0].props.children, /Conexión interrumpida/)
  view(props).props.onKeyDown(key())
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(calls, 2)
})
