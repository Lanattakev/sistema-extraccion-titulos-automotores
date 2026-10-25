import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/services/api.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2023 },
})
const { getDocuments, reviewDocument } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const fields = { patente: 'AB123CD', marca: 'Toyota', modelo: 'Corolla', numero_motor: 'M123', numero_chasis: 'C456', anio: 2020 }
const document = { id_documento: 'doc-1', nombre_original: 'titulo.pdf', ...fields, estado: 'revisado', id_interno: null }

function useFetch(context, implementation) {
  const original = globalThis.fetch
  globalThis.fetch = implementation
  context.after(() => { globalThis.fetch = original })
}

test('recupera los tres estados persistidos y mantiene campos faltantes en null', async (context) => {
  const saved = [
    { ...document, id_documento: 'pending', estado: 'pendiente', marca: null, anio: null },
    document,
    { ...document, id_documento: 'registered', estado: 'registrado', id_interno: 'vehicle-1' },
  ]
  useFetch(context, async (url) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/documents')
    return Response.json(saved)
  })
  assert.deepEqual(await getDocuments(), saved)
})

test('guarda revision mediante PATCH con exactamente los seis campos corregidos', async (context) => {
  useFetch(context, async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:8000/api/v1/documents/doc-1/review')
    assert.equal(options.method, 'PATCH')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), fields)
    return Response.json(document)
  })
  assert.deepEqual(await reviewDocument('doc-1', { ...fields, estado: 'registrado' }), document)
})

test('un PATCH fallido comunica el error sin simular una revision exitosa', async (context) => {
  useFetch(context, async () => Response.json({ detail: 'El documento ya esta registrado.' }, { status: 409 }))
  await assert.rejects(reviewDocument('doc-1', fields), /ya esta registrado/)
})

test('rechaza estados desconocidos, revisiones incompletas y registros sin vinculo', async (context) => {
  useFetch(context, async () => Response.json([{ ...document, estado: 'otro' }]))
  await assert.rejects(getDocuments(), /lista de documentos/)
  globalThis.fetch = async () => Response.json([{ ...document, marca: null }])
  await assert.rejects(getDocuments(), /lista de documentos/)
  globalThis.fetch = async () => Response.json([{ ...document, estado: 'registrado' }])
  await assert.rejects(getDocuments(), /lista de documentos/)
  globalThis.fetch = async () => Response.json({ ...document, estado: 'pendiente' })
  await assert.rejects(reviewDocument('doc-1', fields), /revisión guardada/)
})
