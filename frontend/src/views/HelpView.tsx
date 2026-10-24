import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import type { Page } from '../navigation'

const steps: { title: string; description: string; icon: IconName }[] = [
  { title: 'Cargar', description: 'Reuní los títulos en PDF, JPG, JPEG o PNG. Elegí archivos legibles y completos para facilitar la lectura de la información.', icon: 'upload' },
  { title: 'Revisar', description: 'Verificá patente, marca, modelo, año, número de motor y número de chasis. Corregí cualquier dato que no coincida con el título.', icon: 'file' },
  { title: 'Confirmar', description: 'Con los seis campos verificados, confirmá el registro. El vehículo quedará disponible para consultar desde Vehículos.', icon: 'check' },
]

export function HelpView({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return (
    <div className="view-stack">
      <ol className="help-steps">
        {steps.map((step, index) => <li className="panel help-step" key={step.title}><div className="help-step-top"><span className="metric-icon"><Icon name={step.icon} size={24} /></span><span className="step-number">0{index + 1}</span></div><h2>{step.title}</h2><p>{step.description}</p></li>)}
      </ol>
      <section className="panel help-bottom" aria-labelledby="help-status-title">
        <div><h2 id="help-status-title">Una revisión clara en cada paso</h2><p><strong>Listo:</strong> información disponible. <strong>Revisar:</strong> requiere verificar datos. <strong>Error:</strong> el documento necesita volver a cargarse.</p><p>Estás en una demostración: la carga, la extracción y la confirmación todavía no procesan documentos reales.</p></div>
        <button className="primary-button" type="button" onClick={() => onNavigate('upload')}>Explorar la carga<Icon name="arrow" size={17} /></button>
      </section>
    </div>
  )
}
