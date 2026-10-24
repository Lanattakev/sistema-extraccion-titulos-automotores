import { UploadArea } from '../components/UploadArea'
import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import { VehiclesFeedback } from '../components/VehiclesFeedback'
import type { VehiclesState } from '../types/vehicles'

function HowItWorks() {
  const steps = [['Cargá tus títulos', 'Reuní tus documentos en un solo lugar.'], ['Revisá la información', 'Verificá los datos extraídos del vehículo.'], ['Confirmá y registrá', 'Tu vehículo, organizado y listo para consultar.']]
  return <section className="how-card" aria-labelledby="how-title"><span className="eyebrow">SIMPLE, DE PRINCIPIO A FIN</span><h2 id="how-title">¿Cómo funciona?</h2><ol className="steps">{steps.map(([title, description], index) => <li key={title}><span className="step-number">0{index + 1}</span><div><h3>{title}</h3><p>{description}</p></div></li>)}</ol><div className="human-note"><Icon name="check" size={17} />La última palabra siempre es tuya.</div></section>
}

export function HomeView({ onFilesSelected, vehicleState }: {
  onFilesSelected: (files: File[]) => void
  vehicleState: VehiclesState
}) {
  const { vehicles, loading, error } = vehicleState
  const recent = [...(vehicles ?? [])].sort((a, b) => Date.parse(b.fecha_ingreso) - Date.parse(a.fecha_ingreso)).slice(0, 5)
  const available = !loading && !error && vehicles !== null

  return (
    <div className="view-stack">
      <VehiclesFeedback {...vehicleState} />
      <div className="dashboard-grid">
        <UploadArea onFilesSelected={onFilesSelected} />
        <div className="overview-column">
          <HowItWorks />
          <section className="vehicle-card" aria-labelledby="vehicle-title">
            <div className="vehicle-card-top"><Icon name="car" size={24} /></div>
            <div className="vehicle-summary"><div><h2 id="vehicle-title">Vehículos registrados</h2><strong>{available ? vehicles.length : '—'}<span>{loading ? 'Actualizando…' : error ? 'No disponible' : 'vehículos en tu espacio'}</span></strong></div><Icon name="arrow" size={23} /></div>
            <div className="vehicle-card-footer"><span className="status-dot" />Registros consultados en el backend.</div>
          </section>
        </div>
      </div>
      <section className="documents-card" aria-labelledby="recent-title">
        <div className="table-heading"><div><h2 id="recent-title">Registros recientes</h2><p>Los últimos vehículos guardados, ordenados por fecha de ingreso.</p></div></div>
        {loading && <p className="vehicle-feedback" role="status">Cargando registros recientes…</p>}
        {error && <p className="vehicle-feedback">No se pudo obtener el listado. Reintentá la consulta desde el aviso superior.</p>}
        {available && !recent.length && <p className="vehicle-feedback">Todavía no hay registros. Cargá un título, revisalo y confirmalo para registrar tu primer vehículo.</p>}
        {available && !!recent.length && <div className="table-scroll"><table><caption className="sr-only">Últimos cinco registros vehiculares guardados.</caption><thead><tr>{['Documento', 'Patente', 'Vehículo', 'Ingreso', 'Estado'].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{recent.map((intake) => <tr key={intake.id_interno}><td><div className="document-cell"><span className="file-icon"><Icon name="file" /></span><strong>{intake.archivo_origen}</strong></div></td><td><span className="plate">{intake.vehicle.patente}</span></td><td>{intake.vehicle.marca} {intake.vehicle.modelo}<small>{intake.vehicle.anio}</small></td><td>{new Date(intake.fecha_ingreso).toLocaleString('es-AR')}</td><td><StatusBadge status={intake.requiere_revision ? 'review' : 'registered'} /></td></tr>)}</tbody></table></div>}
      </section>
    </div>
  )
}
