import { Fragment, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { mockVehicles } from '../mockData'

export function VehiclesView() {
  const [expandedPlate, setExpandedPlate] = useState<string | null>(null)

  return (
    <section className="panel" aria-labelledby="vehicles-title">
      <div className="panel-heading"><div><h2 id="vehicles-title">Vehículos del espacio</h2><p>Consultá la ficha de cada vehículo de ejemplo.</p></div><span className="demo-label">Datos de ejemplo</span></div>
      <div className="table-scroll">
        <table>
          <caption className="sr-only">Vehículos ficticios para demostrar el registro vehicular.</caption>
          <thead><tr>{['Patente', 'Marca / modelo', 'Año', 'Estado', 'Acciones'].map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>
            {mockVehicles.map((vehicle, index) => {
              const expanded = expandedPlate === vehicle.plate
              return (
                <Fragment key={vehicle.plate}>
                  <tr>
                    <td><span className="plate">{vehicle.plate}</span></td>
                    <td><strong>{vehicle.brand}</strong><small>{vehicle.model}</small></td>
                    <td>{vehicle.year}</td>
                    <td><StatusBadge status={vehicle.status} /></td>
                    <td><button className="text-button" type="button" aria-expanded={expanded} aria-controls={`vehicle-detail-${index}`} aria-label={`${expanded ? 'Cerrar' : 'Ver'} ficha de ${vehicle.plate}`} onClick={() => setExpandedPlate(expanded ? null : vehicle.plate)}>{expanded ? 'Cerrar ficha' : 'Ver ficha'}</button></td>
                  </tr>
                  <tr id={`vehicle-detail-${index}`} hidden={!expanded} className="detail-row">
                    <td colSpan={5}><div className="vehicle-detail"><strong>{vehicle.brand} {vehicle.model} · {vehicle.year}</strong><p>Patente {vehicle.plate}. {vehicle.status === 'review' ? 'Este ejemplo requiere revisar la información antes de confirmarla.' : 'Información de ejemplo lista para consultar.'}</p><span>Ficha de demostración · No se guardan cambios</span></div></td>
                  </tr>
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="table-footer"><span>3 vehículos de ejemplo</span><span>Tu información, organizada.</span></div>
    </section>
  )
}
