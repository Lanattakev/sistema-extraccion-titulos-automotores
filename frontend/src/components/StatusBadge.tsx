export type DocumentStatus = 'ready' | 'review' | 'error'

const labels: Record<DocumentStatus, string> = {
  ready: 'Listo',
  review: 'Revisar',
  error: 'Error',
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`status-badge ${status}`}><span />{labels[status]}</span>
}
