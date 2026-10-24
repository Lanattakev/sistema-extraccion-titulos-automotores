import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'

export function UploadArea() {
  return <section className="upload-card" aria-labelledby="upload-title">
    <div className="section-heading"><span className="eyebrow">UN NUEVO COMIENZO</span><span className="subtle-tag">Carga de documentos</span></div>
    <div className="drop-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => event.preventDefault()}>
      <div className="upload-illustration"><span className="paper-back" /><span className="paper-front"><Icon name="file" size={35} /></span><span className="upload-bubble"><Icon name="upload" size={17} /></span></div>
      <h2 id="upload-title">Todo empieza con un título.</h2><p>Arrastrá tus archivos hasta acá<br />y dale el primer paso a tu próximo registro.</p>
      <button className="primary-button" type="button" disabled><Icon name="upload" size={17} />Seleccionar archivos</button><div className="file-formats">PDF <span>·</span> JPG <span>·</span> JPEG <span>·</span> PNG</div>
    </div><div className="upload-footnote"><Icon name="check" size={15} /><span>Vos tenés el control. Revisá los datos antes de registrarlos.</span></div>
  </section>
}
function HowItWorks() {
  const steps = [['Cargá tus títulos', 'Reuní tus documentos en un solo lugar.'], ['Revisá la información', 'Verificá los datos extraídos del vehículo.'], ['Confirmá y registrá', 'Tu vehículo, organizado y listo para consultar.']]
  return <section className="how-card" aria-labelledby="how-title"><span className="eyebrow">SIMPLE, DE PRINCIPIO A FIN</span><h2 id="how-title">¿Cómo funciona?</h2><ol className="steps">{steps.map(([title, description], index) => <li key={title}><span className="step-number">0{index + 1}</span><div><h3>{title}</h3><p>{description}</p></div></li>)}</ol><div className="human-note"><Icon name="check" size={17} />La última palabra siempre es tuya.</div></section>
}
const documents = [
  { name: 'Título Toyota Corolla.pdf', detail: 'PDF · 1,8 MB', plate: 'AB 123 CD', vehicle: 'Toyota Corolla', year: '2020', date: '24 oct, 2026', review: false },
  { name: 'Título Volkswagen Polo.jpg', detail: 'JPG · 2,4 MB', plate: 'AC 456 EF', vehicle: 'Volkswagen Polo', year: '2022', date: '24 oct, 2026', review: true },
  { name: 'Título Ford Ranger.pdf', detail: 'PDF · 1,2 MB', plate: 'AD 789 GH', vehicle: 'Ford Ranger', year: '2023', date: '23 oct, 2026', review: false },
]
function DocumentsTable() {
  return <section className="documents-card" aria-labelledby="documents-title"><div className="table-heading"><div><h2 id="documents-title">Documentos procesados <span className="count-badge">03</span></h2><p>Un vistazo a tus últimos movimientos.</p></div><span className="demo-label">Datos de ejemplo</span></div><div className="table-scroll"><table><caption className="sr-only">Documentos de ejemplo; no representan registros reales.</caption><thead><tr>{['Documento', 'Dominio', 'Vehículo', 'Fecha', 'Estado'].map((label) => <th key={label} scope="col">{label}</th>)}</tr></thead><tbody>{documents.map((document) => <tr key={document.plate}><td><div className="document-cell"><span className="file-icon"><Icon name="file" /></span><div><strong>{document.name}</strong><small>{document.detail}</small></div></div></td><td><span className="plate">{document.plate}</span></td><td>{document.vehicle}<small>{document.year}</small></td><td className="date-cell">{document.date}</td><td><StatusBadge status={document.review ? 'review' : 'ready'} /></td></tr>)}</tbody></table></div><div className="table-footer"><span>Mostrando 3 documentos de ejemplo</span><span>Organización que se nota.</span></div></section>
}
function VehicleCard() {
  return <section className="vehicle-card" aria-labelledby="vehicle-title"><div className="vehicle-card-top"><Icon name="car" size={24} /><span className="mock-pill">Ejemplo</span></div><div className="vehicle-summary"><div><h2 id="vehicle-title">Vehículos registrados</h2><strong>128<span>vehículos en tu espacio</span></strong></div><Icon name="arrow" size={23} /></div><div className="vehicle-card-footer"><span className="status-dot" />Cada registro, un paso más de orden.</div></section>
}

export function HomeView() {
  return (
    <>
      <div className="dashboard-grid">
        <UploadArea />
        <div className="overview-column"><HowItWorks /><VehicleCard /></div>
      </div>
      <DocumentsTable />
    </>
  )
}
