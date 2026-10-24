import { Fragment, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { VehiclesFeedback } from '../components/VehiclesFeedback'
import type { VehiclesState } from '../types/vehicles'

export function VehiclesView({ vehicleState }: { vehicleState: VehiclesState }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const { vehicles, loading, error } = vehicleState

  return (
    <div className="view-stack">
      <VehiclesFeedback {...vehicleState} />
      <section className="panel" aria-labelledby="vehicles-title">
        <div className="panel-heading"><div><h2 id="vehicles-title">Vehículos del espacio</h2><p>Registros guardados en el backend.</p></div><button className="text-button" type="button" disabled={loading} onClick={() => void vehicleState.refresh()}>Actualizar</button></div>
        {!loading && !error && vehicles?.length === 0 && <p className="vehicle-feedback">Todavía no hay vehículos registrados. Confirmá un título revisado para comenzar.</p>}
        {!loading && !error && !!vehicles?.length && <div className="table-scroll">
          <table>
            <caption className="sr-only">Vehículos guardados en el registro.</caption>
            <thead><tr>{['Patente', 'Marca / modelo', 'Año', 'Estado', 'Acciones'].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
            <tbody>
              {vehicles.map((intake, index) => {
                const vehicle = intake.vehicle
                const expanded = expandedId === intake.id_interno
                return (
                  <Fragment key={intake.id_interno}>
                    <tr>
                      <td><span className="plate">{vehicle.patente}</span></td>
                      <td><strong>{vehicle.marca}</strong><small>{vehicle.modelo}</small></td>
                      <td>{vehicle.anio}</td>
                      <td><StatusBadge status={intake.requiere_revision ? 'review' : 'registered'} /></td>
                      <td><button className="text-button" type="button" aria-expanded={expanded} aria-controls={`vehicle-detail-${index}`} aria-label={`${expanded ? 'Cerrar' : 'Ver'} ficha de ${vehicle.patente}`} onClick={() => setExpandedId(expanded ? null : intake.id_interno)}>{expanded ? 'Cerrar ficha' : 'Ver ficha'}</button></td>
                    </tr>
                    <tr id={`vehicle-detail-${index}`} hidden={!expanded} className="detail-row">
                      <td colSpan={5}><div className="vehicle-detail"><strong>{vehicle.marca} {vehicle.modelo} · {vehicle.anio}</strong><p>Patente: {vehicle.patente} · Motor: {vehicle.numero_motor} · Chasis: {vehicle.numero_chasis}</p><p>Archivo: {intake.archivo_origen}</p><span>ID: {intake.id_interno} · Ingreso: {new Date(intake.fecha_ingreso).toLocaleString('es-AR')}</span></div></td>
                    </tr>
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>}
        {!loading && !error && vehicles && <div className="table-footer"><span>{vehicles.length} vehículo(s) guardado(s)</span><span>Tu información, organizada.</span></div>}
      </section>
    </div>
  )
}
