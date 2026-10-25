import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/hooks/useDocumentConfirmation.ts', import.meta.url), 'utf8')
const code = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
}).outputText
const fields = { patente: 'AB123CD', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M123', numero_chasis: 'C456', anio: 2020 }
const document = (id, estado = 'pendiente') => ({ id_documento: id, nombre_original: `${id}.pdf`, ...fields, estado, id_interno: estado === 'registrado' ? `vehicle-${id}` : null })

// Controlador aislado con estado y efectos observables; las pruebas HTTP viven en document-workflow.
function controller(api) {
  const states = []
  const effects = []
  const react = {
    useState: initial => {
      const index = states.length
      states.push(initial)
      return [initial, value => { states[index] = typeof value === 'function' ? value(states[index]) : value }]
    },
    useRef: current => ({ current }),
    useCallback: callback => callback,
    useEffect: effect => { effects.push(effect) },
  }
  const module = { exports: {} }
  new Function('require', 'exports', code)(name => name === 'react' ? react : api, module.exports)
  let refreshes = 0
  const hook = module.exports.useDocumentConfirmation(async () => { refreshes++ })
  return { hook, states, effects, refreshes: () => refreshes }
}

test('restaura pendientes, revisados y registrados desde la carga inicial', async () => {
  const { states, effects } = controller({ getDocuments: async () => [document('a'), document('b', 'revisado'), document('c', 'registrado')] })
  const cleanup = effects[0]()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(states[0].a.reviewed, undefined)
  assert.deepEqual(states[0].b.reviewed, fields)
  assert.equal(states[0].c.registered.id_interno, 'vehicle-c')
  assert.equal(states[2].length, 3)
  assert.equal(states[3], false)
  cleanup()
})

test('marca Revisado solo despues del PATCH exitoso y conserva Pendiente ante un fallo', async () => {
  let finish
  const { hook, states } = controller({ reviewDocument: () => new Promise(resolve => { finish = resolve }) })
  const pending = hook.onMarkReviewed('a', fields)
  assert.equal(states[0].a.reviewed, undefined)
  assert.equal(states[0].a.savingReview, true)
  assert.deepEqual(states[2], [])
  await hook.onMarkReviewed('a', fields) // doble clic durante el PATCH
  finish(document('a', 'revisado'))
  await pending
  assert.deepEqual(states[0].a.reviewed, fields)
  assert.equal(states[2][0].estado, 'revisado')
  const failing = controller({ reviewDocument: async () => { throw new Error('No se pudo guardar') } })
  await failing.hook.onMarkReviewed('b', fields)
  assert.equal(failing.states[0].b.reviewed, undefined)
  assert.match(failing.states[0].b.error, /No se pudo guardar/)
})

test('revision multiple parcial y confirmacion omiten pendientes y evitan duplicados', async () => {
  const saved = [document('a'), document('b'), document('c')]
  const calls = []
  const c = controller({
    getDocuments: async () => saved,
    reviewDocument: async id => {
      if (id === 'b') throw new Error('Fallo PATCH')
      const index = saved.findIndex(item => item.id_documento === id)
      saved[index] = document(id, 'revisado')
      return saved[index]
    },
    confirmDocument: async (id, vehicle) => {
      calls.push(id)
      const index = saved.findIndex(item => item.id_documento === id)
      saved[index] = document(id, 'registrado')
      return { vehicle, id_interno: `vehicle-${id}` }
    },
  })
  await Promise.all(['a', 'b', 'c'].map(id => c.hook.onMarkReviewed(id, fields)))
  assert.equal(c.states[0].b.reviewed, undefined)
  assert.equal(calls.length, 0)
  await c.hook.onConfirmSelected(['a', 'b', 'c', 'a'])
  assert.deepEqual(calls, ['a', 'c'])
  assert.equal(c.states[0].a.registered.id_interno, 'vehicle-a')
  await c.hook.onConfirmSelected(['a', 'c'])
  await c.hook.onConfirm('a')
  assert.equal(calls.length, 2)
  assert.equal(c.refreshes(), 1)
})

test('una consulta anterior no pisa una revision terminada mientras esperaba el GET', async () => {
  let finish
  const corrections = { ...fields, modelo: 'Modelo corregido' }
  const c = controller({
    getDocuments: () => new Promise(resolve => { finish = resolve }),
    reviewDocument: async id => ({ ...document(id, 'revisado'), ...corrections }),
  })
  const loading = c.hook.refreshDocuments()
  await c.hook.onMarkReviewed('a', corrections)
  finish([document('a'), document('b')])
  await loading
  assert.deepEqual(c.states[0].a.reviewed, corrections)
  assert.equal(c.states[2].find(item => item.id_documento === 'a').estado, 'revisado')
  assert.equal(c.states[2].find(item => item.id_documento === 'a').modelo, corrections.modelo)
  assert.equal(c.states[2].find(item => item.id_documento === 'b').estado, 'pendiente')
})

test('GET anterior tampoco pisa campos de una segunda revision del mismo estado', async () => {
  let finish
  let queries = 0
  const corrections = { ...fields, marca: 'Honda', modelo: 'Civic' }
  const c = controller({
    getDocuments: () => ++queries === 1 ? Promise.resolve([document('a', 'revisado')])
      : new Promise(resolve => { finish = resolve }),
    reviewDocument: async id => ({ ...document(id, 'revisado'), ...corrections }),
  })
  await c.hook.refreshDocuments()
  const loading = c.hook.refreshDocuments()
  c.hook.onInvalidateReview('a')
  await c.hook.onMarkReviewed('a', corrections)
  finish([document('a', 'revisado')])
  await loading
  assert.deepEqual(c.states[0].a.reviewed, corrections)
  assert.equal(c.states[2][0].modelo, 'Civic')
  assert.equal(c.states[2][0].marca, 'Honda')
})

test('GET antiguo sin el documento conserva la revision guardada mientras esperaba', async () => {
  let finish
  const c = controller({
    getDocuments: () => new Promise(resolve => { finish = resolve }),
    reviewDocument: async id => document(id, 'revisado'),
  })
  const loading = c.hook.refreshDocuments()
  await c.hook.onMarkReviewed('a', fields)
  finish([])
  await loading
  assert.equal(c.states[2].length, 1)
  assert.equal(c.states[2][0].estado, 'revisado')
  assert.deepEqual(c.states[0].a.reviewed, fields)
})

test('una respuesta GET superada por otra consulta no modifica ninguna representacion', async () => {
  const finish = []
  const c = controller({ getDocuments: () => new Promise(resolve => { finish.push(resolve) }) })
  const older = c.hook.refreshDocuments()
  const newer = c.hook.refreshDocuments()
  finish[1]([document('a', 'registrado')])
  await newer
  finish[0]([document('a')])
  await older
  assert.equal(c.states[0].a.registered.id_interno, 'vehicle-a')
  assert.equal(c.states[2][0].estado, 'registrado')
  assert.equal(c.states[2][0].id_interno, 'vehicle-a')
})

test('el resumen recupera POST con respuesta perdida y solo reintenta el fallo real', async () => {
  const saved = new Map(['a', 'b', 'c', 'pending'].map(id => [id, document(id)]))
  const calls = []
  let finalQueryStarted
  const finalQuery = new Promise(resolve => { finalQueryStarted = resolve })
  let finishQuery
  let queries = 0
  let retry = false
  const c = controller({
    getDocuments: async () => {
      queries++
      if (queries === 2) {
        finalQueryStarted()
        return new Promise(resolve => { finishQuery = resolve })
      }
      return [...saved.values()]
    },
    reviewDocument: async id => {
      const reviewed = document(id, 'revisado')
      saved.set(id, reviewed)
      return reviewed
    },
    confirmDocument: async (id, vehicle) => {
      calls.push(id)
      if (id === 'b' && !retry) throw new Error('Fallo real de registro')
      saved.set(id, document(id, 'registrado'))
      if (id === 'a') throw new Error('Respuesta perdida luego del commit')
      return { vehicle, id_interno: `vehicle-${id}` }
    },
  })
  await c.hook.refreshDocuments()
  for (const id of ['a', 'b', 'c']) await c.hook.onMarkReviewed(id, fields)
  const processing = c.hook.onConfirmSelected(['a', 'pending', 'b', 'a', 'c'])
  await finalQuery
  assert.deepEqual(calls, ['a', 'b', 'c'])
  assert.deepEqual(c.states[1].failed, ['a', 'b'])
  assert.deepEqual(c.states[1].registered, ['c'])
  assert.equal(c.states[1].running, true)
  finishQuery([...saved.values()])
  await processing
  assert.deepEqual(c.states[1], { running: false, total: 3, completed: 3, registered: ['a', 'c'], failed: ['b'] })
  assert.equal(c.states[0].a.registered.id_interno, 'vehicle-a')
  assert.equal(c.states[0].a.error, undefined)
  assert.equal(c.states[2].find(item => item.id_documento === 'a').estado, 'registrado')
  assert.match(c.states[0].b.error, /Fallo real/)
  await c.hook.onConfirm('a')
  await c.hook.onConfirmSelected(['a', 'c', 'pending'])
  assert.deepEqual(calls, ['a', 'b', 'c'])
  retry = true
  await c.hook.onConfirmSelected(['a', 'b', 'c', 'pending', 'b'])
  assert.deepEqual(calls, ['a', 'b', 'c', 'b'])
  assert.deepEqual(c.states[1], { running: false, total: 1, completed: 1, registered: ['b'], failed: [] })
  assert.equal(c.refreshes(), 2)
})

test('si el GET final falla no convierte una confirmacion incierta en exitosa', async () => {
  const c = controller({
    reviewDocument: async id => document(id, 'revisado'),
    confirmDocument: async () => { throw new Error('Respuesta perdida') },
    getDocuments: async () => { throw new Error('Consulta no disponible') },
  })
  await c.hook.onMarkReviewed('a', fields)
  await c.hook.onConfirmSelected(['a'])
  assert.deepEqual(c.states[1], { running: false, total: 1, completed: 1, registered: [], failed: ['a'] })
  assert.equal(c.states[0].a.registered, undefined)
  assert.match(c.states[4], /Consulta no disponible/)
})
