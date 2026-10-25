import { useCallback, useEffect, useRef, useState } from 'react'
import { confirmDocument, getDocuments, reviewDocument } from '../services/api'
import type { PersistedDocument } from '../types/documents'
import type { BatchConfirmation, ConfirmationState, ReviewedVehicle } from '../types/vehicles'

export function useDocumentConfirmation(refreshVehicles: () => Promise<void>) {
  const [confirmations, setConfirmations] = useState<Record<string, ConfirmationState>>({})
  const [batchConfirmation, setBatchConfirmation] = useState<BatchConfirmation | null>(null)
  const documents = useRef<Record<string, ConfirmationState>>({})
  const batchRunning = useRef(false)
  const [persistedDocuments, setPersistedDocuments] = useState<PersistedDocument[]>([])
  const persisted = useRef<Record<string, PersistedDocument>>({})
  const [documentsLoading, setDocumentsLoading] = useState(true)
  const [documentsError, setDocumentsError] = useState<string | null>(null)
  const requestNumber = useRef(0)

  const loadDocuments = useCallback(() => {
    const request = ++requestNumber.current
    const before = documents.current
    const persistedBefore = persisted.current
    return getDocuments().then((saved) => {
      if (request !== requestNumber.current) return
      const reconciled: Record<string, PersistedDocument> = {}
      for (const document of saved) {
        const id = document.id_documento
        const current = persisted.current[id]
        // Una escritura terminada durante el GET es más reciente que su respuesta.
        // Registrado es terminal; un GET puede recuperarlo tras una respuesta perdida.
        reconciled[id] = current && (current.estado === 'registrado'
          || (document.estado !== 'registrado' && current !== persistedBefore[id]))
          ? current : persistedResult(document)
      }
      for (const [id, document] of Object.entries(persisted.current)) {
        if (!reconciled[id] && document !== persistedBefore[id]) reconciled[id] = document
      }
      persisted.current = reconciled
      setPersistedDocuments(Object.values(reconciled))
      const next = { ...documents.current }
      for (const document of Object.values(reconciled)) {
        const current = next[document.id_documento]
        if (document.estado !== 'registrado' && (current !== before[document.id_documento] || current?.pending || current?.dirty)) continue
        const reviewed = document.estado === 'pendiente' ? undefined : vehicleFields(document)
        next[document.id_documento] = {
          error: document.estado === 'registrado' ? undefined : current?.error,
          reviewed,
          registered: document.estado === 'registrado' && reviewed && document.id_interno
            ? { vehicle: reviewed, id_interno: document.id_interno } : undefined,
        }
      }
      documents.current = next
      setConfirmations(next)
      setDocumentsError(null)
    }).catch((cause: unknown) => {
      if (request === requestNumber.current) setDocumentsError(cause instanceof Error ? cause.message : 'No se pudieron recuperar los documentos.')
    }).finally(() => {
      if (request === requestNumber.current) setDocumentsLoading(false)
    })
  }, [])

  const refreshDocuments = useCallback(async () => {
    setDocumentsLoading(true)
    await loadDocuments()
  }, [loadDocuments])

  useEffect(() => {
    void loadDocuments()
    return () => { requestNumber.current += 1 }
  }, [loadDocuments])

  function update(documentId: string, state: ConfirmationState) {
    documents.current = { ...documents.current, [documentId]: state }
    setConfirmations(documents.current)
  }

  function savePersisted(document: PersistedDocument) {
    persisted.current = { ...persisted.current, [document.id_documento]: persistedResult(document) }
    setPersistedDocuments(Object.values(persisted.current))
  }

  async function onMarkReviewed(documentId: string, fields: ReviewedVehicle) {
    const current = documents.current[documentId]
    if (batchRunning.current || current?.pending || current?.registered) return
    const textFields = ['patente', 'marca', 'modelo', 'numero_motor', 'numero_chasis'] as const
    if (textFields.some((key) => typeof fields[key] !== 'string' || !fields[key].trim())
      || !Number.isSafeInteger(fields.anio) || fields.anio <= 0) return
    update(documentId, { ...current, pending: true, savingReview: true, error: undefined })
    try {
      const saved = await reviewDocument(documentId, fields)
      update(documentId, { reviewed: vehicleFields(saved) })
      savePersisted(saved)
    } catch (cause) {
      update(documentId, { ...current, error: cause instanceof Error ? cause.message : 'No se pudo guardar la revisión.' })
    }
  }

  function onInvalidateReview(documentId: string) {
    const current = documents.current[documentId]
    if (batchRunning.current || current?.pending || current?.registered) return
    update(documentId, { dirty: true })
  }

  async function confirmOne(documentId: string): Promise<'registered' | 'failed' | 'skipped'> {
    const current = documents.current[documentId]
    if (!current?.reviewed || current.pending || current.registered) return 'skipped'
    // Bloqueo sincrónico compartido por confirmación individual y múltiple.
    update(documentId, { ...current, pending: true, error: undefined })
    try {
      const registered = await confirmDocument(documentId, current.reviewed)
      update(documentId, { reviewed: current.reviewed, registered })
      const saved = persisted.current[documentId]
      if (saved) savePersisted({ ...saved, ...registered.vehicle, estado: 'registrado', id_interno: registered.id_interno })
      return 'registered'
    } catch (cause) {
      update(documentId, { reviewed: current.reviewed, error: cause instanceof Error ? cause.message : 'No se pudo confirmar el documento.' })
      return 'failed'
    }
  }

  async function onConfirm(documentId: string) {
    if (batchRunning.current) return
    // Consultar también tras un fallo permite actualizar las vistas si el servidor
    // guardó el vehículo pero se perdió la respuesta de confirmación.
    if (await confirmOne(documentId) !== 'skipped') await Promise.all([refreshVehicles(), refreshDocuments()])
  }

  async function onConfirmSelected(documentIds: string[]) {
    if (batchRunning.current) return
    const eligible = [...new Set(documentIds)].filter((id) => {
      const document = documents.current[id]
      return document?.reviewed && !document.pending && !document.registered
    })
    if (!eligible.length) return
    batchRunning.current = true
    const progress: BatchConfirmation = { running: true, total: eligible.length, completed: 0, registered: [], failed: [] }
    setBatchConfirmation({ ...progress })
    try {
      // Cada resultado se maneja por separado; un fallo no interrumpe los demás.
      for (const id of eligible) {
        const outcome = await confirmOne(id)
        if (outcome === 'registered') progress.registered.push(id)
        if (outcome === 'failed') progress.failed.push(id)
        progress.completed += 1
        setBatchConfirmation({ ...progress, registered: [...progress.registered], failed: [...progress.failed] })
      }
    } finally {
      // Una consulta final actualiza el estado compartido de Inicio y Vehículos.
      try {
        await Promise.all([refreshVehicles(), refreshDocuments()])
      } finally {
        // El GET puede acreditar un registro cuyo POST perdió la respuesta.
        progress.registered = eligible.filter((id) => progress.registered.includes(id) || !!documents.current[id]?.registered)
        progress.failed = progress.failed.filter((id) => !progress.registered.includes(id))
        batchRunning.current = false
        setBatchConfirmation({ ...progress, running: false })
      }
    }
  }

  return { confirmations, batchConfirmation, persistedDocuments, documentsLoading, documentsError, refreshDocuments, onMarkReviewed, onInvalidateReview, onConfirm, onConfirmSelected }
}

function persistedResult(document: PersistedDocument): PersistedDocument {
  return { ...document, fallo: false, requiere_revision: document.estado !== 'registrado' }
}

function vehicleFields(document: PersistedDocument): ReviewedVehicle {
  return {
    patente: document.patente!, marca: document.marca!, modelo: document.modelo!,
    numero_motor: document.numero_motor!, numero_chasis: document.numero_chasis!, anio: document.anio!,
  }
}
