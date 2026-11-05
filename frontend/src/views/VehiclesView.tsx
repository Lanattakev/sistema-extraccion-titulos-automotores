import { Fragment, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { VehiclesFeedback } from '../components/VehiclesFeedback'
import type { ConfirmationProps, VehiclesState } from '../types/vehicles'
import type { HistoryState } from '../types/history'
import { StateSortHeader } from '../components/StateSortHeader'
import { downloadVehiclesCsv } from '../utils/vehiclesCsv'
import { formatRegistrationNumber } from '../utils/registrationNumber'
import { registryRows, searchRegistryRows } from '../utils/registryRows'
import { documentAgingLabel, documentLoadTimes, documentReviewTimes, orderByPriority } from '../utils/documentTiming'
import type { DocumentFilter, PriorityOrder } from '../utils/documentTiming'

export function VehiclesView({ vehicleState, documentState, historyState, now = new Date() }: {
  vehicleState: VehiclesState
  documentState?: Pick<ConfirmationProps, 'persistedDocuments' | 'documentsLoading' | 'documentsError' | 'refreshDocuments'>
  historyState?: HistoryState
  now?: Date
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [order, setOrder] = useState<PriorityOrder>('normal')
  const [statusFilter, setStatusFilter] = useState<DocumentFilter>('todos')
  const { vehicles, loading, error } = vehicleState
  const canExport = !loading && !error && !!vehicles?.length
  const rows = registryRows(documentState && !documentState.documentsLoading && !documentState.documentsError ? documentState.persistedDocuments : [],
    !loading && !error ? vehicles ?? [] : [])
  const loaded = documentLoadTimes(historyState?.events ?? [], now)
  const reviewed = documentReviewTimes(historyState?.events ?? [], loaded, now)
  const visibleRows = orderByPriority(searchRegistryRows(rows, query).filter(row => statusFilter === 'todos' || row.status === statusFilter), order,
    row => row.status, row => row.document ? loaded.get(row.document.id_documento) : undefined)

  function handleExport() {
    if (canExport && vehicles) downloadVehiclesCsv(vehicles)
  }

  return (
    <div className="view-stack">
      <VehiclesFeedback {...vehicleState} />
      {documentState?.documentsLoading && <p className="vehicle-feedback" role="status">Cargando documentos…</p>}
      {documentState?.documentsError && <div className="batch-alert" role="alert"><p>{documentState.documentsError}</p><button className="text-button" type="button" onClick={() => void documentState.refreshDocuments()}>Reintentar documentos</button></div>}
      {historyState?.error && <p className="vehicle-feedback">No se pudieron recuperar las fechas para calcular Aging. {historyState.error}</p>}
      <section className="panel" aria-labelledby="vehicles-title">
        <div className="panel-heading">
          <div><h2 id="vehicles-title">Registros del espacio</h2><p>Documentos pendientes, revisados y vehículos registrados. El N.º de registro se asigna al registrar.</p></div>
          <div className="vehicles-actions">
            <button className="text-button" type="button" disabled={loading || documentState?.documentsLoading} onClick={() => void Promise.all([vehicleState.refresh(), documentState?.refreshDocuments(), historyState?.refresh()])}>Actualizar</button>
            <button className="primary-button" type="button" disabled={!canExport} onClick={handleExport}>Exportar CSV</button>
          </div>
        </div>
        <div className="list-controls">
          <label htmlFor="vehicle-search">Buscar por N.º de registro o patente
            <input id="vehicle-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Ej.: 001 o LPY452" />
          </label>
          <label htmlFor="registry-status">Estado<select id="registry-status" value={statusFilter} onChange={event => setStatusFilter(event.target.value as DocumentFilter)}><option value="todos">Todos</option><option value="pendiente">Pendientes</option><option value="revisado">Revisados</option><option value="registrado">Registrados</option></select></label>
          <span role="status">{visibleRows.length} de {rows.length} registro(s)</span>
        </div>
        {!!rows.length && !visibleRows.length && <p className="vehicle-feedback">No hay registros que coincidan con la búsqueda y el estado.</p>}
        {!loading && !error && vehicles?.length === 0 && <p className="vehicle-feedback">Todavía no hay vehículos registrados. No hay vehículos para exportar. Confirmá un título revisado para comenzar.</p>}
        {!!rows.length && <div className="table-scroll">
          <table>
            <caption className="sr-only">Documentos y vehículos guardados. Estado ↕: orden normal; ↑: mayor prioridad; ↓: menor prioridad.</caption>
            <thead><tr>{['N.º registro', 'Patente', 'Marca / modelo', 'Año'].map((label) => <th scope="col" key={label}>{label}</th>)}<StateSortHeader order={order} onChange={setOrder} /><th scope="col">Tiempo / Aging</th><th scope="col">Acciones</th></tr></thead>
            <tbody>
              {visibleRows.map((row, index) => {
                const intake = row.intake
                const vehicle = intake?.vehicle ?? row.document!
                const expanded = expandedId === row.key
                const ingress = row.document ? loaded.get(row.document.id_documento) : intake?.fecha_ingreso
                const number = intake ? formatRegistrationNumber(intake.numero_registro) : '—'
                const aging = historyState?.loading || historyState?.error ? 'Fecha no disponible' : documentAgingLabel(row.document?.id_documento, row.status, loaded, reviewed, now)
                return (
                  <Fragment key={row.key}>
                    <tr>
                      <td>{number}</td>
                      <td><span className="plate">{vehicle.patente ?? 'No informada'}</span></td>
                      <td><strong>{vehicle.marca ?? 'No informada'}</strong><small>{vehicle.modelo ?? 'No informado'}</small></td>
                      <td>{vehicle.anio ?? '—'}</td>
                      <td><StatusBadge status={row.status === 'pendiente' ? 'pending-review' : row.status === 'revisado' ? 'reviewed' : 'registered'} /></td>
                      <td className="document-aging">{aging}</td>
                      <td><button className="text-button" type="button" aria-expanded={expanded} aria-controls={`vehicle-detail-${index}`} aria-label={`${expanded ? 'Cerrar' : 'Ver'} ficha de ${vehicle.patente ?? row.document?.nombre_original}`} onClick={() => setExpandedId(expanded ? null : row.key)}>{expanded ? 'Cerrar ficha' : 'Ver ficha'}</button></td>
                    </tr>
                    <tr id={`vehicle-detail-${index}`} hidden={!expanded} className="detail-row">
                      <td colSpan={7}><div className="vehicle-detail"><strong>{vehicle.marca} {vehicle.modelo} · {vehicle.anio}</strong><p>Patente: {vehicle.patente} · Motor: {vehicle.numero_motor ?? 'No informado'} · Chasis: {vehicle.numero_chasis ?? 'No informado'}</p><p>Archivo: {intake?.archivo_origen ?? row.document?.nombre_original}</p><span>N.º registro: {number} · Ingreso: {ingress !== undefined ? new Date(ingress).toLocaleString('es-AR') : 'No informado'}</span></div></td>
                    </tr>
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>}
        {!!rows.length && <div className="table-footer"><span>{rows.length} registro(s) guardado(s)</span><span>Tu información, organizada.</span></div>}
      </section>
    </div>
  )
}
