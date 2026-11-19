import { useId, useState } from 'react'
import { documentContentUrl } from '../services/api'

export function DocumentPreview({ documentId, name }: { documentId: string; name: string }) {
  const id = useId()
  const [zoom, setZoom] = useState(100)
  const [failed, setFailed] = useState(false)
  const url = documentContentUrl(documentId)
  const isPdf = /\.pdf$/i.test(name)
  const isImage = /\.(png|jpe?g)$/i.test(name)
  const description = name || 'Documento original'

  return (
    <section className="document-preview" aria-labelledby={`${id}-title`}>
      <h5 id={`${id}-title`}>Documento original</h5>
      <p className="document-preview-name">{description}</p>
      <a href={url} target="_blank" rel="noopener noreferrer">Abrir original en otra pestaña</a>
      {failed ? <div className="batch-alert" role="alert"><p>No se pudo mostrar el original. Podés abrirlo en otra pestaña o reintentar.</p><button type="button" className="text-button" onClick={() => setFailed(false)}>Reintentar vista previa</button></div>
        : isPdf ? <><p>Usá los controles del visor PDF para ampliar y recorrer las páginas. Si no se muestra, abrí el original en otra pestaña.</p><iframe src={url} title={`Documento original: ${description}`} className="document-preview-pdf" onError={() => setFailed(true)} /></>
        : isImage ? <>
          <div className="document-preview-controls" role="group" aria-label="Zoom del documento original">
            <button type="button" className="text-button" disabled={zoom <= 50} onClick={() => setZoom(current => Math.max(50, current - 25))}>Alejar imagen</button>
            <output aria-label="Zoom de la imagen" aria-live="polite">{zoom}%</output>
            <button type="button" className="text-button" disabled={zoom >= 250} onClick={() => setZoom(current => Math.min(250, current + 25))}>Acercar imagen</button>
            <button type="button" className="text-button" disabled={zoom === 100} onClick={() => setZoom(100)}>Restablecer zoom</button>
          </div>
          <p id={`${id}-help`}>Al ampliar, recorré el documento con las barras de desplazamiento, el teclado o el gesto táctil.</p>
          <div className="document-preview-image" role="region" aria-label="Vista del documento original" aria-describedby={`${id}-help`} tabIndex={0}>
            <img src={url} alt={`Documento original: ${description}`} style={{ width: `${zoom}%` }} onError={() => setFailed(true)} />
          </div>
        </> : <p role="status">Este formato no admite una vista previa. Abrí el original en otra pestaña.</p>}
    </section>
  )
}
