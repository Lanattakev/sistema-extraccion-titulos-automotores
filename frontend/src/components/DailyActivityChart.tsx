import type { HistoryEvent } from '../types/history'
import { dailyDocumentActivity } from '../utils/dailyActivity'

export function DailyActivityChart({ events, start, end, now, label }: {
  events: HistoryEvent[]; start: Date; end: Date; now: Date; label: string
}) {
  const days = dailyDocumentActivity(events, start, end, now)
  if (!days.length) return <p className="vehicle-feedback">No hay historial suficiente para reconstruir la actividad diaria de este período.</p>
  const maxTotal = Math.max(...days.map(day => day.total), 1)
  const registrations = days.reduce((sum, day) => sum + day.registered, 0)
  const pendingAtLastCut = days.at(-1)!.pending
  return (
    <figure className="daily-activity" aria-label={`Actividad diaria de ${label}`}>
      <figcaption>
        <strong>Actividad diaria · {label}</strong>
        <p>Pendientes al cierre de cada día y documentos registrados durante ese día. Hoy se muestra hasta ahora.</p>
      </figcaption>
      <div className="daily-legend"><span><i className="daily-pending" aria-hidden="true" />Pendientes</span><span><i className="daily-registered" aria-hidden="true" />Registrados</span></div>
      <p className="daily-totals">Pendientes al último corte: <strong>{pendingAtLastCut}</strong> · Registrados en el período: <strong>{registrations}</strong></p>
      <ol className="daily-bars">
        {days.map(day => <li key={day.date}>
          <time dateTime={day.date}>{day.date}{day.partial && <small>Hasta ahora</small>}</time>
          <div className="daily-stack" role="img" aria-label={`${day.date}: ${day.pending} pendientes, ${day.registered} registrados, total de la barra ${day.total}${day.partial ? ', hasta ahora' : ', al cierre'}`}>
            <span className="daily-pending" style={{ width: `${day.pending / maxTotal * 100}%` }} />
            <span className="daily-registered" style={{ width: `${day.registered / maxTotal * 100}%` }} />
          </div>
          <span className="daily-values">P: {day.pending} · R: {day.registered} · Total: <strong>{day.total}</strong></span>
        </li>)}
      </ol>
      <p className="daily-note">P = pendientes con carga conocida, aún sin revisión ni registro. R = registrados ese día. El total de cada barra suma ambas series; no representa documentos únicos del período. Los pendientes se cuentan nuevamente en cada día que esperan. No se muestran días anteriores al primer evento disponible.</p>
    </figure>
  )
}
