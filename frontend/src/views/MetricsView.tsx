import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'

function MetricCard({ title, value, note, icon }: { title: string; value: string; note: string; icon: IconName }) {
  return <article className="panel metric-card"><span className="metric-icon"><Icon name={icon} /></span><h2>{title}</h2><strong>{value}</strong><p>{note}</p></article>
}

const weeklyActivity = [
  { day: 'Lun', count: 12 }, { day: 'Mar', count: 18 }, { day: 'Mié', count: 15 },
  { day: 'Jue', count: 24 }, { day: 'Vie', count: 20 }, { day: 'Sáb', count: 8 }, { day: 'Dom', count: 3 },
]
const distribution = [
  { status: 'ready', value: 78 }, { status: 'review', value: 18 }, { status: 'error', value: 4 },
] as const

export function MetricsView() {
  return (
    <div className="view-stack">
      <div className="notice"><Icon name="chart" /><p>Todos los indicadores son ilustrativos. Período de ejemplo: 19 al 25 de octubre de 2026.</p></div>
      <div className="metrics-grid">
        <MetricCard title="Vehículos registrados" value="128" note="Total acumulado de ejemplo" icon="car" />
        <MetricCard title="Documentos de la semana" value="100" note="Actividad ilustrativa del período" icon="file" />
        <MetricCard title="Pendientes de revisión" value="18" note="Documentos que necesitan tu atención" icon="history" />
        <MetricCard title="Documentos listos" value="78%" note="Sobre los documentos del período" icon="check" />
      </div>
      <div className="charts-grid">
        <section className="panel" aria-labelledby="activity-title">
          <div className="panel-heading"><div><h2 id="activity-title">Actividad semanal</h2><p>Documentos procesados por día · Ejemplo</p></div></div>
          <div className="bar-chart" role="img" aria-label={`Documentos por día. ${weeklyActivity.map(({ day, count }) => `${day}: ${count}`).join(', ')}.`}>
            {weeklyActivity.map(({ day, count }) => <div className="chart-column" key={day}><div className="bar-track"><div className="chart-bar" style={{ height: `${count / 24 * 100}%` }}><span>{count}</span></div></div><span className="chart-day">{day}</span></div>)}
          </div>
        </section>
        <section className="panel" aria-labelledby="distribution-title">
          <div className="panel-heading"><div><h2 id="distribution-title">Estado de los documentos</h2><p>Distribución del período · Ejemplo</p></div></div>
          <div className="distribution-list">
            {distribution.map(({ status, value }) => <div key={status}><div className="distribution-label"><StatusBadge status={status} /><strong>{value}%</strong></div><div className={`distribution-track ${status}`} role="meter" aria-label={{ ready: 'Listo', review: 'Revisar', error: 'Error' }[status]} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${value}%` }} /></div></div>)}
          </div>
        </section>
      </div>
    </div>
  )
}
