import { useEffect, useRef, useState } from 'react'
import { DocumentReview } from '../components/DocumentReview'
import type { ConfirmationProps, ReviewedVehicle } from '../types/vehicles'
import { Icon } from '../components/Icon'
import { UploadArea } from '../components/UploadArea'
import { StatusBadge } from '../components/StatusBadge'
import { uploadDocumentBatch } from '../services/api'
import type { BatchDocumentResult } from '../types/documents'
import './UploadView.css'

const extractedFields = [
  ['patente', 'Patente'], ['marca', 'Marca'], ['modelo', 'Modelo'],
  ['numero_motor', 'Número de motor'], ['numero_chasis', 'Número de chasis'], ['anio', 'Año'],
] as const

function BatchResult({ result, selected, onSelect, draft, onDraftChange, ...confirmationProps }: ConfirmationProps & {
  result: BatchDocumentResult
  selected: boolean
  draft?: ReviewedVehicle
  onDraftChange: (fields: ReviewedVehicle) => void
  onSelect: (selected: boolean) => void
}) {
  const { confirmations, batchConfirmation } = confirmationProps
  const [reviewing, setReviewing] = useState(false)
  const confirmation = result.id_documento ? confirmations[result.id_documento] : undefined
  const canReview = !!result.id_documento && result.fallo === false && !result.error
  const canSelect = canReview && !confirmation?.registered && !confirmation?.pending

  const status = confirmation?.registered ? 'registered' : confirmation?.reviewed ? 'reviewed' : result.fallo === true || result.error ? 'error'
    : canReview ? 'pending-review'
    : result.fallo === false ? 'ready' : null

  return (
    <li className={`batch-result${selected && canSelect ? ' is-selected' : ''}`}>
      <div className="batch-result-heading">
        <input type="checkbox" aria-label={`Seleccionar ${result.nombre_original ?? result.id_documento}`} checked={selected && canSelect} disabled={!canSelect || batchConfirmation?.running} onChange={(event) => onSelect(event.target.checked)} />
        <span className="file-icon"><Icon name="file" /></span>
        <h3>{result.nombre_original ?? 'Nombre no informado'}</h3>
        {canReview && !confirmation?.registered
          ? <button className="review-trigger" type="button" onClick={() => setReviewing(true)} disabled={confirmation?.pending || batchConfirmation?.running} aria-expanded={reviewing}><StatusBadge status={confirmation?.reviewed ? 'reviewed' : 'pending-review'} /></button>
          : status ? <StatusBadge status={status} /> : <span className="subtle-tag">Estado no informado</span>}
      </div>
      <dl className="batch-fields">
        <div className="document-id"><dt>ID del documento</dt><dd>{result.id_documento ?? 'No informado'}</dd></div>
        {extractedFields.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{(confirmation?.registered?.vehicle[key] ?? confirmation?.reviewed?.[key] ?? result[key]) ?? 'No informado'}</dd></div>)}
        <div><dt>Requiere revisión</dt><dd>{confirmation?.registered ? 'No' : result.requiere_revision === undefined ? 'No informado' : result.requiere_revision ? 'Sí' : 'No'}</dd></div>
        <div><dt>Fallo</dt><dd>{result.fallo === undefined ? 'No informado' : result.fallo ? 'Sí' : 'No'}</dd></div>
      </dl>
      {result.error && <p className="batch-file-error"><strong>Error:</strong> {result.error}</p>}
      {confirmation?.error && !reviewing && <p className="batch-file-error" role="alert"><strong>No se completó la operación:</strong> {confirmation.error}</p>}
      {confirmation?.pending && <p role="status">{confirmation.savingReview ? 'Guardando revisión...' : 'Registrando documento...'}</p>}
      {confirmation?.registered && <div className="registration-success" role="status"><Icon name="check" /><div><strong>Vehículo registrado correctamente.</strong><p>{confirmation.registered.vehicle.patente} · ID {confirmation.registered.id_interno}</p></div></div>}
      {reviewing && canReview && !confirmation?.registered && <DocumentReview result={result} draft={draft} onDraftChange={onDraftChange} {...confirmationProps} onInvalidateReview={(id) => { onSelect(false); confirmationProps.onInvalidateReview(id) }} onClose={() => setReviewing(false)} />}
    </li>
  )
}

export function UploadView({ initialFiles = [], ...confirmationProps }: ConfirmationProps & { initialFiles?: File[] }) {
  const { confirmations, batchConfirmation, onConfirmSelected } = confirmationProps
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [drafts, setDrafts] = useState<Record<string, ReviewedVehicle>>({})
  const [files, setFiles] = useState<File[]>(initialFiles)
  const [batchResults, setResults] = useState<BatchDocumentResult[] | null>(null)
  const results = batchResults ?? confirmationProps.persistedDocuments
  const [reviewingBatch, setReviewingBatch] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  // Todas las acciones y cantidades se limitan a los resultados visibles.
  const currentDocuments = [...new Map((results ?? []).flatMap((result) =>
    result.id_documento && result.fallo === false && !result.error
      ? [[result.id_documento, result] as const] : [],
  )).values()]
  const pendingDocuments = currentDocuments.filter((result) => {
    const state = confirmations[result.id_documento!]
    return !state?.reviewed && !state?.registered
  })
  const reviewedDocuments = currentDocuments.filter((result) => {
    const state = confirmations[result.id_documento!]
    return state?.reviewed && !state.registered
  })
  const selectableIds = reviewedDocuments.flatMap((result) =>
    !confirmations[result.id_documento!]?.pending ? [result.id_documento!] : [],
  )
  const eligibleSelectedIds = selectableIds.filter((id) => selectedIds.has(id))
  const selectedCount = currentDocuments.filter((result) => {
    const id = result.id_documento!
    return selectedIds.has(id) && !confirmations[id]?.registered && !confirmations[id]?.pending
  }).length
  const registeredCount = currentDocuments.filter((result) => confirmations[result.id_documento!]?.registered).length
  const reviewCandidates = pendingDocuments.flatMap((result) => {
    const id = result.id_documento!
    if (confirmations[id]?.pending) return []
    const fields = drafts[id] ?? result
    if (extractedFields.some(([key]) => key !== 'anio'
      && (typeof fields[key] !== 'string' || !fields[key].trim()))
      || !Number.isSafeInteger(fields.anio) || !fields.anio || fields.anio <= 0) return []
    return [{ id, fields: {
      patente: fields.patente!, marca: fields.marca!, modelo: fields.modelo!,
      numero_motor: fields.numero_motor!, numero_chasis: fields.numero_chasis!, anio: fields.anio,
    } }]
  })
  const bulkDisabled = loading || reviewingBatch || confirmationProps.documentsLoading || !!batchConfirmation?.running
  const selectedReviewCandidates = reviewCandidates.filter(({ id }) => selectedIds.has(id))

  async function markReviewed(candidates: typeof reviewCandidates) {
    if (bulkDisabled) return
    setReviewingBatch(true)
    try {
      await Promise.all(candidates.map(({ id, fields }) => confirmationProps.onMarkReviewed(id, fields)))
    } finally {
      setReviewingBatch(false)
    }
  }

  function markSelectedReviewed() {
    void markReviewed(selectedReviewCandidates)
  }

  useEffect(() => () => requestRef.current?.abort(), [])

  function addFiles(selected: File[]) {
    if (requestRef.current || reviewingBatch || batchConfirmation?.running) return
    setFiles((current) => [...current, ...selected])
    setResults(null)
    setDrafts({})
    setSelectedIds(new Set())
    setError(null)
  }

  async function submitBatch() {
    if (!files.length || requestRef.current || reviewingBatch || batchConfirmation?.running) return
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError(null)
    setResults(null)
    setDrafts({})
    setSelectedIds(new Set())
    try {
      const batch = await uploadDocumentBatch(files, controller.signal)
      if (!controller.signal.aborted) {
        setResults(batch)
        setFiles([])
        await confirmationProps.refreshDocuments()
      }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : 'Ocurrió un error al procesar el lote.')
    } finally {
      if (!controller.signal.aborted) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }

  return (
    <div className="view-stack">
      <div className="notice"><Icon name="file" /><p>Cargá tus títulos para extraer los datos. Revisá la información devuelta antes de registrar un vehículo.</p></div>
      <UploadArea onFilesSelected={addFiles} loading={loading || reviewingBatch || batchConfirmation?.running} />
      <section className="panel" aria-labelledby="files-title">
        <div className="panel-heading"><div><h2 id="files-title">Archivos del lote</h2><p>{files.length ? `${files.length} archivo(s) seleccionado(s)` : 'Seleccioná o arrastrá archivos para comenzar.'}</p></div></div>
        {files.length > 0 && <ul className="file-list">{files.map((file, index) => (
          <li key={`${file.name}-${index}`}>
            <span className="file-icon"><Icon name="file" /></span>
            <div className="file-description"><h3>{file.name}</h3><small>{(file.size / 1024).toLocaleString('es-AR', { maximumFractionDigits: 1 })} KB</small></div>
            <button className="text-button" type="button" disabled={loading || batchConfirmation?.running} aria-label={`Quitar ${file.name}`} onClick={() => setFiles((current) => current.filter((_, position) => position !== index))}>Quitar</button>
          </li>
        ))}</ul>}
        <div className="batch-actions"><button className="primary-button" type="button" disabled={loading || !files.length || batchConfirmation?.running} onClick={submitBatch}>{loading ? 'Procesando lote…' : 'Procesar archivos'}</button><p role="status">{loading ? 'Enviando y extrayendo los datos. Esto puede tardar unos instantes.' : results !== null ? `${results.length} resultado(s) recibido(s).` : 'Los archivos se envían al presionar Procesar archivos.'}</p></div>
      </section>
      {error && <div className="batch-alert" role="alert"><strong>No se completó el procesamiento.</strong><p>{error}</p><p>Los archivos siguen seleccionados. Podés volver a intentar el envío.</p></div>}
      {confirmationProps.documentsLoading && <p role="status">Recuperando documentos guardados...</p>}
      {confirmationProps.documentsError && <div className="batch-alert" role="alert"><p>{confirmationProps.documentsError}</p><button className="text-button" type="button" onClick={() => void confirmationProps.refreshDocuments()}>Reintentar consulta</button></div>}
      <section className="panel" aria-label="Confirmación múltiple">
        <div className="batch-actions" role="status" aria-live="polite">
          <p>Pendientes: <strong>{pendingDocuments.length}</strong></p>
          <p>Revisados: <strong>{reviewedDocuments.length}</strong></p>
          <p>Seleccionados: <strong>{selectedCount}</strong></p>
          <p>Registrados: <strong>{registeredCount}</strong></p>
        </div>
        <div className="batch-actions">
          <button className="primary-button" type="button" disabled={bulkDisabled || !reviewCandidates.length} onClick={() => void markReviewed(reviewCandidates)}>Marcar todos como revisados</button>
          <button className="primary-button" type="button" disabled={bulkDisabled || !selectedReviewCandidates.length} onClick={markSelectedReviewed}>Marcar seleccionados como revisados</button>
          <button className="text-button" type="button" disabled={bulkDisabled || !selectableIds.length} onClick={() => { if (!bulkDisabled) setSelectedIds(new Set(selectableIds)) }}>Seleccionar todos los revisados</button>
          <button className="text-button" type="button" disabled={bulkDisabled || !selectedIds.size} onClick={() => { if (!bulkDisabled) setSelectedIds(new Set()) }}>Deseleccionar todos</button>
          <p>Marcar como revisado no registra vehículos. Los documentos con datos incompletos o con fallos se omiten.</p>
          {reviewingBatch && <p role="status">Guardando las revisiones seleccionadas...</p>}
        </div>
        <div className="batch-actions">
          <button className="primary-button" type="button" disabled={bulkDisabled || !eligibleSelectedIds.length} onClick={() => void onConfirmSelected(eligibleSelectedIds)}>Confirmar seleccionados</button>
          <p role="status">{eligibleSelectedIds.length} documento(s) revisado(s) seleccionado(s).</p>
          <p>Solo se registran documentos marcados como Revisado.</p>
        </div>
        {batchConfirmation && <div className="bulk-summary" role="status" aria-live="polite"><p>{batchConfirmation.running ? 'Confirmando documentos' : 'Confirmación finalizada'}: {batchConfirmation.completed} de {batchConfirmation.total}</p><progress max={batchConfirmation.total} value={batchConfirmation.completed} aria-label="Progreso de confirmación" /><p>{batchConfirmation.registered.length} registrado(s) · {batchConfirmation.failed.length} fallido(s)</p>{batchConfirmation.registered.length > 0 && <p>Registrados: {batchConfirmation.registered.map((id) => results?.find((result) => result.id_documento === id)?.nombre_original ?? id).join(', ')}</p>}{batchConfirmation.failed.length > 0 && <p>No registrados: {batchConfirmation.failed.map((id) => results?.find((result) => result.id_documento === id)?.nombre_original ?? id).join(', ')}</p>}</div>}
      </section>
      {results !== null && <section className="panel" aria-labelledby="results-title"><div className="panel-heading"><div><h2 id="results-title">Resultados del lote</h2><p>Información devuelta por el servidor. Los campos ausentes se muestran como “No informado”.</p></div></div>{results.length ? <ul className="batch-results">{results.map((result, index) => <BatchResult {...confirmationProps} draft={result.id_documento ? drafts[result.id_documento] : undefined} onDraftChange={(fields) => { if (result.id_documento) { const id = result.id_documento; setDrafts((current) => ({ ...current, [id]: fields })) } }} selected={!!result.id_documento && selectedIds.has(result.id_documento)} onSelect={(checked) => { if (!result.id_documento || batchConfirmation?.running) return; const id = result.id_documento; const state = confirmations[id]; if (checked && (state?.pending || state?.registered || result.fallo !== false || result.error)) return; setSelectedIds((current) => { const next = new Set(current); if (checked) next.add(id); else next.delete(id); return next }) }} key={`${result.id_documento ?? 'document'}-${index}`} result={result} />)}</ul> : <p className="batch-empty">El servidor no devolvió resultados para este lote.</p>}</section>}
    </div>
  )
}
