import { useRef, useState } from 'react'
import { Icon } from './Icon'
import '../views/UploadView.css'

export function UploadArea({ onFilesSelected, loading = false }: {
  onFilesSelected: (files: File[]) => void
  loading?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  function addFiles(incoming: FileList | File[]) {
    if (loading) return
    const selected = Array.from(incoming)
    if (!selected.length) return
    const isValid = (file: File) => /\.(pdf|jpe?g|png)$/i.test(file.name) && file.size > 0
    const invalid = selected.filter((file) => !isValid(file))
    setValidationError(invalid.length
      ? `No se agregaron: ${invalid.map((file) => file.name).join(', ')}. Usá PDF, JPG, JPEG o PNG que no estén vacíos.`
      : null)
    const valid = selected.filter(isValid)
    if (valid.length) onFilesSelected(valid)
  }

  return (
    <>
      <section className="upload-card" aria-labelledby="upload-title" aria-busy={loading}>
        <div className="section-heading"><span className="eyebrow">UN NUEVO COMIENZO</span><span className="subtle-tag">Carga de documentos</span></div>
        <div
          className={`drop-zone ${dragging ? 'is-dragging' : ''}`}
          onDragEnter={(event) => { event.preventDefault(); dragDepth.current += 1; if (!loading) setDragging(true) }}
          onDragOver={(event) => { event.preventDefault(); event.dataTransfer.dropEffect = loading ? 'none' : 'copy' }}
          onDragLeave={(event) => { event.preventDefault(); dragDepth.current -= 1; if (dragDepth.current <= 0) setDragging(false) }}
          onDrop={(event) => { event.preventDefault(); dragDepth.current = 0; setDragging(false); addFiles(event.dataTransfer.files) }}
        >
          <div className="upload-illustration"><span className="paper-back" /><span className="paper-front"><Icon name="file" size={35} /></span><span className="upload-bubble"><Icon name="upload" size={17} /></span></div>
          <h2 id="upload-title">Todo empieza con un título.</h2>
          <p>Arrastrá tus archivos hasta acá<br />o seleccioná varios documentos para armar un lote.</p>
          <input ref={inputRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png" className="sr-only" tabIndex={-1} aria-label="Archivos del lote" disabled={loading} onChange={(event) => { if (event.target.files) addFiles(event.target.files); event.target.value = '' }} />
          <button className="primary-button" type="button" disabled={loading} onClick={() => inputRef.current?.click()}><Icon name="upload" size={17} />Seleccionar archivos</button>
          <div className="file-formats">PDF <span>·</span> JPG <span>·</span> JPEG <span>·</span> PNG</div>
        </div>
        <div className="upload-footnote"><Icon name="check" size={15} /><span>Vos tenés el control. Revisá los datos antes de registrarlos.</span></div>
      </section>
      {validationError && <div className="batch-alert" role="alert">{validationError}</div>}
    </>
  )
}
