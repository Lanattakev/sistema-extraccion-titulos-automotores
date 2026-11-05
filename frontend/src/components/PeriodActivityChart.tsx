import type { documentRegistrationPeriods } from '../utils/metrics'

export function PeriodActivityChart({ periods, label }: {
  periods: ReturnType<typeof documentRegistrationPeriods>; label: string
}) {
  const maxTotal = Math.max(...periods.map(period => period.total), 1)
  const registered = periods.reduce((sum, period) => sum + period.registered, 0)
  const pending = periods.reduce((sum, period) => sum + period.pending, 0)
  return <figure className="period-activity" aria-label={label}>
    <figcaption>
      <div className="period-legend"><span><i className="period-registered" aria-hidden="true" />Registrados</span><span><i className="period-pending" aria-hidden="true" />Pendientes de registro</span></div>
      <p>Documentos cargados en cada período, clasificados por su estado actual. Pendiente de registro incluye Pendientes y Revisados. Los documentos sin fecha de carga conocida no se incluyen.</p>
    </figcaption>
    {!registered && !pending && <p className="vehicle-feedback">No hay documentos con fecha de carga conocida en estos períodos.</p>}
    <ol className="period-bars">
      {periods.map(period => <li key={period.isoLabel}>
        <span className="period-label" title={period.isoLabel}>{period.label}<small>{period.isoLabel !== period.label ? period.isoLabel : ''}</small></span>
        <div className="period-chart-row">
          <div className="period-stack" role="img" aria-label={`${period.label} (${period.isoLabel}): ${period.registered} registrados, ${period.pending} pendientes de registro, total ${period.total}`}>
            <span className="period-registered" style={{ width: `${period.registered / maxTotal * 100}%` }} />
            <span className="period-pending" style={{ width: `${period.pending / maxTotal * 100}%` }} />
          </div>
          <span className="period-values">{period.registered} registrados / {period.pending} pendientes de registro</span>
        </div>
        <strong className="period-total">Total {period.total}</strong>
      </li>)}
    </ol>
    <p className="period-totals">{registered} registrados / {pending} pendientes de registro · Total {registered + pending}</p>
  </figure>
}
