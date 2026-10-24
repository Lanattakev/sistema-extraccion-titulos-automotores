import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import { mockOperations } from '../mockData'

export function HistoryView() {
  return (
    <section className="panel" aria-labelledby="history-title">
      <div className="panel-heading"><div><h2 id="history-title">Operaciones recientes</h2><p>Un recorrido por la actividad de ejemplo.</p></div><span className="demo-label">Datos de ejemplo</span></div>
      <ol className="operation-list">
        {mockOperations.map((operation) => (
          <li key={operation.id}>
            <span className="operation-icon"><Icon name={operation.status === 'ready' ? 'check' : 'file'} /></span>
            <div className="operation-description"><span className="operation-id">{operation.id} · Operador</span><h3>{operation.title}</h3><p>{operation.document}</p></div>
            <div className="operation-time">{operation.date}<small>{operation.time}</small></div>
            <StatusBadge status={operation.status} />
          </li>
        ))}
      </ol>
    </section>
  )
}
