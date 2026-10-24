import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

// Compila en memoria con TypeScript ya instalado; no requiere otro runner.
const source = await readFile(new URL('../src/services/api.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 },
})
const { uploadDocumentBatch, confirmDocument, getVehicles } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

function mockFetch(context, implementation) {
  const original = globalThis.fetch
  globalThis.fetch = implementation
  context.after(() => { globalThis.fetch = original })
}

test('envía todos los archivos bajo files y conserva resultados mixtos sin inventar campos', async (context) => {
  const files = [new File(['pdf'], 'titulo.pdf'), new File(['png'], 'foto.png')]
  const results = [
    { id_documento: 'documento-1', nombre_original: 'titulo.pdf', patente: 'AB123CD', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M1', numero_chasis: 'C1', anio: 2020, requiere_revision: true, fallo: false, error: null },
    { id_documento: null, nombre_original: 'foto.png', fallo: true, error: 'No se pudo leer' },
  ]
  mockFetch(context, async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/documents/batch')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers, undefined)
    assert.deepEqual([...options.body.keys()], ['files', 'files'])
    assert.deepEqual(options.body.getAll('files').map((file) => file.name), ['titulo.pdf', 'foto.png'])
    return Response.json(results)
  })
  assert.deepEqual(await uploadDocumentBatch(files), results)
})

test('muestra los errores detail de FastAPI y los errores HTTP sin JSON', async (context) => {
  mockFetch(context, async () => Response.json({ detail: [{ msg: 'Debe enviar archivos en files.' }] }, { status: 422 }))
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')]), /Debe enviar archivos en files/)
  globalThis.fetch = async () => new Response('Unavailable', { status: 503 })
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')]), /HTTP 503/)
})

test('rechaza respuestas exitosas con un formato inválido', async (context) => {
  mockFetch(context, async () => Response.json([{ fallo: 'false', patente: 123 }]))
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')]), /respuesta de lote inválida/)
  globalThis.fetch = async () => new Response('<html>Error</html>')
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')]), /respuesta de lote inválida/)
})

test('informa fallos de conexión y permite cancelar con AbortSignal', async (context) => {
  mockFetch(context, async () => { throw new TypeError('Failed to fetch') })
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')]), /No se pudo conectar con el servidor/)
  const controller = new AbortController()
  controller.abort()
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.signal, controller.signal)
    throw new DOMException('Aborted', 'AbortError')
  }
  await assert.rejects(uploadDocumentBatch([new File(['x'], 'a.pdf')], controller.signal), { name: 'AbortError' })
})

test('no envía lotes vacíos y conserva una respuesta vacía', async (context) => {
  let calls = 0
  mockFetch(context, async () => { calls++; return Response.json([]) })
  await assert.rejects(uploadDocumentBatch([]), /Seleccioná al menos un archivo/)
  assert.equal(calls, 0)
  assert.deepEqual(await uploadDocumentBatch([new File(['x'], 'a.pdf')]), [])
})

const reviewed = { patente: 'CD456EF', marca: 'Honda', modelo: 'Civic', numero_motor: 'M2', numero_chasis: 'C2', anio: 2022 }
const saved = { vehicle: reviewed, archivo_origen: 'titulo.pdf', id_interno: 'registro-1', fecha_ingreso: '2026-10-24T12:00:00Z', requiere_revision: false }

test('confirma con los seis campos corregidos, año numérico y sin metadatos del documento', async (context) => {
  mockFetch(context, async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/documents/doc-1/confirm')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), reviewed)
    return Response.json(saved, { status: 201 })
  })
  assert.deepEqual(await confirmDocument('doc-1', { ...reviewed, id_documento: 'no-enviar', requiere_revision: true }), saved)
})

test('consulta vehículos reales y conserva un registro vacío sin fallback mock', async (context) => {
  mockFetch(context, async (url) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/vehicles')
    return Response.json([saved])
  })
  assert.deepEqual(await getVehicles(), [saved])
  globalThis.fetch = async () => Response.json([])
  assert.deepEqual(await getVehicles(), [])
  globalThis.fetch = async () => Response.json([{ patente: 'formato-incorrecto' }])
  await assert.rejects(getVehicles(), /lista de vehículos inválida/)
})

test('propaga errores de confirmación y de consulta sin fabricar registros', async (context) => {
  mockFetch(context, async () => Response.json({ detail: 'Documento no encontrado.' }, { status: 404 }))
  await assert.rejects(confirmDocument('no-existe', reviewed), /Documento no encontrado/)
  globalThis.fetch = async () => { throw new TypeError('offline') }
  await assert.rejects(getVehicles(), /No se pudo conectar con el backend/)
  globalThis.fetch = async () => Response.json(null)
  await assert.rejects(confirmDocument('doc-1', reviewed), /sin una ficha válida/)
})

test('bloquea doble clic y una segunda confirmación después del éxito', async (context) => {
  // Ejecuta el controlador del hook con refs estables, sin montar una UI ni enviar datos reales.
  const hookSource = await readFile(new URL('../src/hooks/useDocumentConfirmation.ts', import.meta.url), 'utf8')
  const hooks = 'data:text/javascript;base64,' + Buffer.from('export const useRef = (current) => ({ current }); export const useState = () => [undefined, () => {}];').toString('base64')
  const apiModule = 'data:text/javascript;base64,' + Buffer.from(outputText).toString('base64')
  const compiled = ts.transpileModule(hookSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 } }).outputText
    .replace(/from ['"]react['"]/, `from '${hooks}'`)
    .replace(/from ['"]\.\.\/services\/api['"]/, `from '${apiModule}'`)
  const { useDocumentConfirmation } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'))
  let complete
  let requests = 0
  let refreshes = 0
  mockFetch(context, () => {
    requests++
    return new Promise((resolve) => { complete = () => resolve(Response.json(saved, { status: 201 })) })
  })
  const { onConfirm, onMarkReviewed } = useDocumentConfirmation(async () => { refreshes++ })
  onMarkReviewed('doc-1', reviewed)
  const pending = onConfirm('doc-1')
  await onConfirm('doc-1')
  assert.equal(requests, 1)
  complete()
  await pending
  await onConfirm('doc-1')
  assert.equal(requests, 1)
  assert.equal(refreshes, 1)
})

let controllerNumber = 0
async function confirmationController(refresh) {
  const hookSource = await readFile(new URL('../src/hooks/useDocumentConfirmation.ts', import.meta.url), 'utf8')
  const hooks = 'data:text/javascript;base64,' + Buffer.from(`export const updates = []; export const useRef = (current) => ({ current }); export const useState = (initial) => { const index = updates.length; updates.push(initial); return [initial, value => { updates[index] = value }]; }; // ${controllerNumber++}`).toString('base64')
  const apiModule = 'data:text/javascript;base64,' + Buffer.from(outputText).toString('base64')
  const compiled = ts.transpileModule(hookSource, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 } }).outputText
    .replace(/from ['"]react['"]/, `from '${hooks}'`)
    .replace(/from ['"]\.\.\/services\/api['"]/, `from '${apiModule}'`)
  const { useDocumentConfirmation } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'))
  const { updates } = await import(hooks)
  return { controller: useDocumentConfirmation(refresh), updates }
}

test('marcar revisado no persiste y editar obliga a revisar nuevamente', async (context) => {
  let requests = 0
  mockFetch(context, async () => { requests++; return Response.json(saved, { status: 201 }) })
  const { controller, updates } = await confirmationController(async () => {})
  await controller.onConfirm('pendiente')
  controller.onMarkReviewed('doc-1', reviewed)
  assert.equal(requests, 0)
  assert.deepEqual(updates[0]['doc-1'].reviewed, reviewed)
  controller.onInvalidateReview('doc-1')
  await controller.onConfirm('doc-1')
  assert.equal(requests, 0)
  controller.onMarkReviewed('doc-1', { ...reviewed, modelo: 'Civic corregido' })
  await controller.onConfirm('doc-1')
  assert.equal(requests, 1)
  assert.ok(updates[0]['doc-1'].registered)
})

test('confirmación múltiple omite pendientes, continúa tras un fallo y no duplica éxitos', async (context) => {
  const calls = []
  let refreshes = 0
  mockFetch(context, async (url, options) => {
    const id = url.split('/').at(-2)
    calls.push({ id, fields: JSON.parse(options.body) })
    return id === 'doc-2' ? Response.json({ detail: 'Error del segundo documento' }, { status: 400 }) : Response.json(saved, { status: 201 })
  })
  const { controller, updates } = await confirmationController(async () => { refreshes++ })
  controller.onMarkReviewed('doc-1', reviewed)
  controller.onMarkReviewed('doc-2', { ...reviewed, modelo: 'Segundo' })
  controller.onMarkReviewed('doc-3', { ...reviewed, modelo: 'Tercero' })
  const processing = controller.onConfirmSelected(['doc-1', 'pendiente', 'doc-2', 'doc-1', 'doc-3'])
  await controller.onConfirmSelected(['doc-1', 'doc-2'])
  await controller.onConfirm('doc-3')
  await processing
  assert.deepEqual(calls.map(({ id }) => id), ['doc-1', 'doc-2', 'doc-3'])
  assert.equal(calls[1].fields.modelo, 'Segundo')
  assert.equal(calls[2].fields.modelo, 'Tercero')
  assert.deepEqual(updates[1], { running: false, total: 3, completed: 3, registered: ['doc-1', 'doc-3'], failed: ['doc-2'] })
  assert.match(updates[0]['doc-2'].error, /Error del segundo documento/)
  assert.ok(updates[0]['doc-3'].registered)
  assert.equal(refreshes, 1)
  await controller.onConfirmSelected(['doc-1', 'doc-3', 'pendiente'])
  await controller.onConfirm('doc-1')
  assert.equal(calls.length, 3)
  await controller.onConfirmSelected(['doc-2'])
  assert.equal(calls.length, 4)
  assert.equal(refreshes, 2)
})
