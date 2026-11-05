import { Icon } from '../components/Icon'
import { PeriodActivityChart } from '../components/PeriodActivityChart'
import type { IconName } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import { VehiclesFeedback } from '../components/VehiclesFeedback'
import type { ConfirmationProps, VehiclesState } from '../types/vehicles'
import { documentMetrics, documentTimeMetrics, documentRegistrationPeriods, topBrands } from '../utils/metrics'
import { formatDuration } from '../utils/documentTiming'
import type { HistoryState } from '../types/history'

function MetricCard({ title, value, note, icon }: { title: string; value: string; note: string; icon: IconName }) {
  return <article className="panel metric-card"><span className="metric-icon"><Icon name={icon} /></span><h2>{title}</h2><strong>{value}</strong><p>{note}</p></article>
}

const format = (value: number) => value.toLocaleString('es-AR', { maximumFractionDigits: 1 })
const emptyMessage = 'Aún no hay datos suficientes para mostrar esta métrica.'

export function MetricsView({ vehicleState, documentState, historyState, now }: {
  vehicleState: VehiclesState
  documentState: Pick<ConfirmationProps, 'persistedDocuments' | 'documentsLoading' | 'documentsError' | 'refreshDocuments'>
  historyState: HistoryState
  now: Date
}) {
  const { persistedDocuments, documentsLoading, documentsError, refreshDocuments } = documentState
  const documentsAvailable = !documentsLoading && !documentsError
  const vehiclesAvailable = !vehicleState.loading && !vehicleState.error && vehicleState.vehicles !== null
  const metrics = documentMetrics(persistedDocuments)
  const brands = topBrands(vehicleState.vehicles ?? [])
  const maxBrandCount = brands[0]?.count ?? 0
  const historyAvailable = !historyState.loading && !historyState.error && historyState.events !== null
  const times = documentTimeMetrics(persistedDocuments, historyState.events ?? [], now)
  const weeks = documentRegistrationPeriods(persistedDocuments, historyState.events ?? [], now, 'week')
  const months = documentRegistrationPeriods(persistedDocuments, historyState.events ?? [], now, 'month')
  const documentValue = (value: number) => documentsAvailable ? format(value) : '—'
  const distribution = [
    { status: 'pending-review', label: 'Pendiente', count: metrics.pendiente },
    { status: 'reviewed', label: 'Revisado', count: metrics.revisado },
    { status: 'registered', label: 'Registrado', count: metrics.registrado },
  ] as const
  return (
    <div className="view-stack">
      <div className="notice"><Icon name="chart" /><p>Indicadores calculados a partir de tus documentos guardados y vehículos registrados.</p></div>
      <VehiclesFeedback {...vehicleState} />
      {historyState.loading && <p className="vehicle-feedback" role="status">Actualizando fechas del historial…</p>}
      {historyState.error && <div className="batch-alert" role="alert"><p>{historyState.error}</p><button className="text-button" type="button" onClick={() => void historyState.refresh()}>Reintentar historial</button></div>}
      {documentsLoading && <p className="vehicle-feedback" role="status">Actualizando documentos…</p>}
      {documentsError && <div className="batch-alert" role="alert"><p><strong>No se pudieron actualizar los documentos.</strong> {documentsError}</p><button className="text-button" type="button" onClick={() => void refreshDocuments()}>Reintentar consulta</button></div>}
      <div className="metrics-grid">
        <MetricCard title="Vehículos registrados" value={vehiclesAvailable ? format(vehicleState.vehicles!.length) : '—'} note="Total de vehículos guardados" icon="car" />
        <MetricCard title="Documentos totales" value={documentValue(metrics.total)} note="Total de documentos persistidos" icon="file" />
        <MetricCard title="Pendientes de revisión" value={documentValue(metrics.pendiente)} note="Documentos pendientes de validación" icon="history" />
        <MetricCard title="Revisados" value={documentValue(metrics.revisado)} note="Documentos revisados sin registrar" icon="check" />
        <MetricCard title="Registrados" value={documentValue(metrics.registrado)} note="Documentos con registro completado" icon="file" />
        <MetricCard title="Porcentaje registrado" value={documentsAvailable ? `${format(metrics.registeredPercentage)}%` : '—'} note="Documentos registrados sobre el total" icon="chart" />
        <MetricCard title="Tiempo promedio de revisión" value={historyAvailable ? formatDuration(times.reviewAverage) : '—'} note={historyAvailable ? `${times.reviewCount} documento(s) con carga y primera revisión válidas` : 'Esperando fechas del historial'} icon="check" />
        <MetricCard title="Antigüedad promedio de pendientes" value={historyAvailable && documentsAvailable ? formatDuration(times.pendingAverage) : '—'} note={historyAvailable && documentsAvailable ? `${times.pendingCount} pendiente(s) con fecha de carga conocida` : 'Esperando documentos e historial'} icon="history" />
      </div>
      <div className="charts-grid">
        {[{ id: 'weeks', title: 'Registros de las últimas 6 semanas', periods: weeks, note: 'Seis semanas ISO consecutivas, de la más antigua a la actual. Lunes a domingo, hora local.' },
          { id: 'months', title: 'Registros de los últimos 3 meses', periods: months, note: 'Tres meses consecutivos, del más antiguo al actual, hora local.' }].map(({ id, title, periods, note }) => (
          <section className="panel" aria-labelledby={`${id}-title`} key={id}>
            <div className="panel-heading"><div><h2 id={`${id}-title`}>{title}</h2><p>{note}</p></div></div>
            {historyAvailable && documentsAvailable ? <PeriodActivityChart periods={periods} label={title} />
              : <p className="vehicle-feedback">{historyState.loading || documentsLoading ? 'Cargando actividad por período…' : 'La actividad por período estará disponible al recuperar documentos e historial.'}</p>}
          </section>
        ))}
      </div>
      <div className="charts-grid">
        <section className="panel" aria-labelledby="brands-title">
          <div className="panel-heading"><div><h2 id="brands-title">Top marcas</h2><p>Marcas con más vehículos registrados. Barras relativas a la marca con mayor cantidad.</p></div></div>
          {vehiclesAvailable && brands.length > 0 ? <div className="distribution-list">
            {brands.map(({ brand, count }) => <div key={brand}><div className="distribution-label"><span>{brand}</span><strong>{format(count)}</strong></div><div className="distribution-track" role="meter" aria-label={`Vehículos ${brand}`} aria-valuenow={count} aria-valuemin={0} aria-valuemax={maxBrandCount} aria-valuetext={`${count} vehículos`}><span style={{ width: `${count / maxBrandCount * 100}%` }} /></div></div>)}
          </div> : <p className="vehicle-feedback">{vehicleState.loading ? 'Cargando marcas…' : !vehiclesAvailable ? 'La métrica estará disponible cuando se recuperen los vehículos.' : emptyMessage}</p>}
        </section>
        <section className="panel" aria-labelledby="distribution-title">
          <div className="panel-heading"><div><h2 id="distribution-title">Distribución de documentos</h2><p>Pendiente / Revisado / Registrado</p></div></div>
          {documentsAvailable && metrics.total > 0 ? <div className="distribution-list">
            {distribution.map(({ status, label, count }) => {
              const percentage = count / metrics.total * 100
              return <div key={status}><div className="distribution-label"><StatusBadge status={status} /><strong>{format(count)} · {format(percentage)}%</strong></div><div className={`distribution-track ${status}`} role="meter" aria-label={label} aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100} aria-valuetext={`${count} documentos, ${format(percentage)}%`}><span style={{ width: `${percentage}%` }} /></div></div>
            })}
          </div> : <p className="vehicle-feedback">{documentsLoading ? 'Cargando distribución…' : !documentsAvailable ? 'La métrica estará disponible cuando se recuperen los documentos.' : emptyMessage}</p>}
        </section>
      </div>
    </div>
  )
}
