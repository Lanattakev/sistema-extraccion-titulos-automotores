import { useId, useState } from 'react'
import type { FormEvent } from 'react'
import type { BatchDocumentResult } from '../types/documents'
import type { ConfirmationProps, ReviewedVehicle } from '../types/vehicles'

const fields = [
  ['patente', 'Patente'], ['marca', 'Marca'], ['modelo', 'Modelo'],
  ['numero_motor', 'Número de motor'], ['numero_chasis', 'Número de chasis'], ['anio', 'Año'],
] as const

export function DocumentReview({ result, confirmations, batchConfirmation, onMarkReviewed, onInvalidateReview, onConfirm, onClose, draft, onDraftChange }: ConfirmationProps & {
  result: BatchDocumentResult
  draft?: ReviewedVehicle
  onDraftChange: (fields: ReviewedVehicle) => void
  onClose: () => void
}) {
  const id = useId()
  const reviewed = result.id_documento ? confirmations[result.id_documento]?.reviewed : undefined
  const initial = draft ?? reviewed ?? result
  const [values, setValues] = useState(() => ({
    patente: initial.patente ?? '', marca: initial.marca ?? '', modelo: initial.modelo ?? '',
    numero_motor: initial.numero_motor ?? '', numero_chasis: initial.numero_chasis ?? '',
    anio: initial.anio?.toString() ?? '',
  }))
  const [validationError, setValidationError] = useState<string | null>(null)
  const confirmation = result.id_documento ? confirmations[result.id_documento] : undefined

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!result.id_documento || confirmation?.pending || confirmation?.registered || batchConfirmation?.running) return
    const year = Number(values.anio)
    if (Object.values(values).some((value) => !value.trim()) || !Number.isSafeInteger(year) || year <= 0) {
      setValidationError('Completá los seis campos. El año debe ser un entero mayor que cero.')
      return
    }
    setValidationError(null)
    onMarkReviewed(result.id_documento, { ...values, anio: year })
  }

  return (
    <form className="document-review" onSubmit={submit} aria-labelledby={`${id}-title`}>
      <h4 id={`${id}-title`}>Revisá la información del título</h4>
      <p>Corregí los datos y marcá el documento como revisado. El vehículo solo se registra al confirmar.</p>
      <fieldset disabled={confirmation?.pending || !!confirmation?.registered || batchConfirmation?.running}>
        <legend className="sr-only">Datos del vehículo</legend>
        <div className="review-fields">
          {fields.map(([key, label]) => <div key={key}><label htmlFor={`${id}-${key}`}>{label}</label><input id={`${id}-${key}`} name={key} type={key === 'anio' ? 'number' : 'text'} min={key === 'anio' ? 1 : undefined} step={key === 'anio' ? 1 : undefined} required value={values[key]} onChange={(event) => { if (result.id_documento) onInvalidateReview(result.id_documento); const next = { ...values, [key]: event.target.value }; setValues(next); onDraftChange({ ...next, anio: Number(next.anio) }) }} /></div>)}
        </div>
      </fieldset>
      {validationError && <p className="batch-file-error" role="alert">{validationError}</p>}
      {confirmation?.error && <div className="batch-alert" role="alert"><p>{confirmation.error}</p><p>Si se interrumpió la conexión, consultá Vehículos antes de reintentar: el servidor podría haber guardado el registro.</p></div>}
      <div className="review-actions">
        <button className="primary-button" type="submit" disabled={confirmation?.pending || !!confirmation?.registered || batchConfirmation?.running || !result.id_documento}>Marcar como revisado</button>
        <button className="primary-button" type="button" disabled={!confirmation?.reviewed || confirmation?.pending || !!confirmation?.registered || batchConfirmation?.running} onClick={() => { if (result.id_documento) void onConfirm(result.id_documento) }}>{confirmation?.pending ? 'Registrando...' : 'Confirmar y registrar'}</button>
        <button className="text-button" type="button" onClick={onClose} disabled={confirmation?.pending}>Cerrar revisión</button>
      </div>
      {confirmation?.pending && <p role="status">Confirmando el registro. Esperá la respuesta del servidor.</p>}
    </form>
  )
}
