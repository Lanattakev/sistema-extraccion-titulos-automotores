export function PageHeading({ title, description }: { title: string; description: string }) {
  return (
    <div className="page-intro">
      <div>
        <div className="intro-label"><span />MENOS PROCESOS. MÁS SIMPLEZA.</div>
        <h1 id="page-title" tabIndex={-1}>{title}</h1>
        <p>{description}</p>
      </div>
      <span className="preview-badge">Vista de demostración</span>
    </div>
  )
}
