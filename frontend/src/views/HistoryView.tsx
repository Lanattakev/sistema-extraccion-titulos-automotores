import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import type { DocumentStatus } from '../components/StatusBadge'
import { useHistory } from '../hooks/useHistory'
import type { HistoryEvent } from '../types/history'

const actions: Record<HistoryEvent['tipo_evento'], { title: string; status: DocumentStatus }> = {
  documento_cargado: { title: 'Documento cargado', status: 'pending-review' },
  documento_revisado: { title: 'Documento revisado', status: 'reviewed' },
  documento_registrado: { title: 'Documento registrado', status: 'registered' },
}

export function HistoryView() {
  const { events, loading, error, refresh } = useHistory()
  return (
    <section className="panel" aria-labelledby="history-title">
      <div className="panel-heading"><div><h2 id="history-title">Operaciones recientes</h2><p>Eventos guardados del ciclo documental, del más reciente al más antiguo.</p></div><button className="text-button" type="button" disabled={loading} onClick={() => void refresh()}>Actualizar</button></div>
      {loading && <p className="vehicle-feedback" role="status">Cargando historial…</p>}
      {error && <div className="batch-alert" role="alert"><p><strong>No se pudo recuperar el historial.</strong> {error}</p><button className="text-button" type="button" disabled={loading} onClick={() => void refresh()}>Reintentar consulta</button></div>}
      {!loading && !error && events?.length === 0 && <p className="vehicle-feedback">Todavía no hay eventos en el historial.</p>}
      {!loading && !error && !!events?.length && <ol className="operation-list">
        {events.map(event => {
          const action = actions[event.tipo_evento]
          const date = new Date(event.fecha_evento)
          return <li key={event.id_evento}>
            <span className="operation-icon"><Icon name={event.tipo_evento === 'documento_cargado' ? 'file' : 'check'} /></span>
            <div className="operation-description"><span className="operation-id">Documento: {event.id_documento}</span><h3>{action.title}</h3><p>{event.nombre_original}</p><span className="operation-id">Evento: {event.id_evento}</span></div>
            <time className="operation-time" dateTime={event.fecha_evento}>{date.toLocaleDateString('es-AR')}<small>{date.toLocaleTimeString('es-AR')}</small></time>
            <StatusBadge status={action.status} />
          </li>
        })}
      </ol>}
    </section>
  )
}
