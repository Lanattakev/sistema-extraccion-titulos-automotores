import { Icon } from '../components/Icon'
import { StatusBadge } from '../components/StatusBadge'
import { mockFiles } from '../mockData'
import { UploadArea } from './HomeView'

export function UploadView() {
  return (
    <div className="view-stack">
      <div className="notice"><Icon name="file" /><p><strong>Una vista previa del flujo de carga.</strong> Los archivos de la lista son ejemplos. La carga y el procesamiento todavía no están habilitados.</p></div>
      <UploadArea />
      <section className="panel" aria-labelledby="files-title">
        <div className="panel-heading"><div><h2 id="files-title">Archivos del lote</h2><p>Tres ejemplos de los estados de un documento.</p></div><span className="demo-label">Datos de ejemplo</span></div>
        <ul className="file-list">
          {mockFiles.map((file) => (
            <li key={file.name}>
              <span className="file-icon"><Icon name="file" /></span>
              <div className="file-description"><h3>{file.name}</h3><small>{file.detail}</small><p>{file.message}</p></div>
              <StatusBadge status={file.status} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
