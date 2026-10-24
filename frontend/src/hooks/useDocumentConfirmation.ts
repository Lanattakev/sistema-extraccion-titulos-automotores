import { useRef, useState } from 'react'
import { confirmDocument } from '../services/api'
import type { BatchConfirmation, ConfirmationState, ReviewedVehicle } from '../types/vehicles'

export function useDocumentConfirmation(refreshVehicles: () => Promise<void>) {
  const [confirmations, setConfirmations] = useState<Record<string, ConfirmationState>>({})
  const [batchConfirmation, setBatchConfirmation] = useState<BatchConfirmation | null>(null)
  const documents = useRef<Record<string, ConfirmationState>>({})
  const batchRunning = useRef(false)

  function update(documentId: string, state: ConfirmationState) {
    documents.current = { ...documents.current, [documentId]: state }
    setConfirmations(documents.current)
  }

  function onMarkReviewed(documentId: string, fields: ReviewedVehicle) {
    const current = documents.current[documentId]
    if (batchRunning.current || current?.pending || current?.registered) return
    const textFields = ['patente', 'marca', 'modelo', 'numero_motor', 'numero_chasis'] as const
    if (textFields.some((key) => typeof fields[key] !== 'string' || !fields[key].trim())
      || !Number.isSafeInteger(fields.anio) || fields.anio <= 0) return
    update(documentId, { reviewed: { ...fields } })
  }

  function onInvalidateReview(documentId: string) {
    const current = documents.current[documentId]
    if (batchRunning.current || current?.pending || current?.registered) return
    update(documentId, {})
  }

  async function confirmOne(documentId: string): Promise<'registered' | 'failed' | 'skipped'> {
    const current = documents.current[documentId]
    if (!current?.reviewed || current.pending || current.registered) return 'skipped'
    // Bloqueo sincrónico compartido por confirmación individual y múltiple.
    update(documentId, { ...current, pending: true, error: undefined })
    try {
      const registered = await confirmDocument(documentId, current.reviewed)
      update(documentId, { reviewed: current.reviewed, registered })
      return 'registered'
    } catch (cause) {
      update(documentId, { reviewed: current.reviewed, error: cause instanceof Error ? cause.message : 'No se pudo confirmar el documento.' })
      return 'failed'
    }
  }

  async function onConfirm(documentId: string) {
    if (batchRunning.current) return
    if (await confirmOne(documentId) === 'registered') await refreshVehicles()
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
        await refreshVehicles()
      } finally {
        batchRunning.current = false
        setBatchConfirmation({ ...progress, running: false })
      }
    }
  }

  return { confirmations, batchConfirmation, onMarkReviewed, onInvalidateReview, onConfirm, onConfirmSelected }
}
