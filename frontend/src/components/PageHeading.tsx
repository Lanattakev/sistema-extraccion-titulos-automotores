export function PageHeading({ title, description, demo = true }: { title: string; description: string; demo?: boolean }) {
  return (
    <div className="page-intro">
      <div>
        <div className="intro-label"><span />MENOS PROCESOS. MÁS SIMPLEZA.</div>
        <h1 id="page-title" tabIndex={-1}>{title}</h1>
        <p>{description}</p>
      </div>
      {demo && <span className="preview-badge">Vista de demostración</span>}
    </div>
  )
}
