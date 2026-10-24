export type DocumentStatus = 'ready' | 'review' | 'error' | 'registered' | 'pending-review' | 'reviewed'

const labels: Record<DocumentStatus, string> = {
  ready: 'Listo',
  review: 'Revisar',
  error: 'Error',
  registered: 'Registrado',
  'pending-review': 'Pendiente de revisión',
  reviewed: 'Revisado',
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`status-badge ${status}`}><span />{labels[status]}</span>
}
