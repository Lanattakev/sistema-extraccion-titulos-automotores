import type { DocumentStatus } from './components/StatusBadge'

// Fixtures de demostración: no se leen ni se guardan registros reales.
export const mockVehicles: {
  plate: string; brand: string; model: string; year: number; status: DocumentStatus
}[] = [
  { plate: 'AB 123 CD', brand: 'Toyota', model: 'Corolla', year: 2020, status: 'ready' },
  { plate: 'AC 456 EF', brand: 'Volkswagen', model: 'Polo', year: 2022, status: 'review' },
  { plate: 'AD 789 GH', brand: 'Ford', model: 'Ranger', year: 2023, status: 'ready' },
]

export const mockFiles: {
  name: string; detail: string; message: string; status: DocumentStatus
}[] = [
  { name: 'Título Toyota Corolla.pdf', detail: 'PDF · 1,8 MB', message: 'Información disponible para consultar.', status: 'ready' },
  { name: 'Título Volkswagen Polo.jpg', detail: 'JPG · 2,4 MB', message: 'Verificá los campos antes de confirmar.', status: 'review' },
  { name: 'Título escaneado.png', detail: 'PNG · 980 KB', message: 'No se pudo leer el documento. Probá con una imagen más nítida.', status: 'error' },
]

export const mockOperations: {
  id: string; title: string; document: string; date: string; time: string; status: DocumentStatus
}[] = [
  { id: 'OP-004', title: 'Documento procesado', document: 'Título Toyota Corolla.pdf', date: '24 oct, 2026', time: '10:42', status: 'ready' },
  { id: 'OP-003', title: 'Revisión pendiente', document: 'Título Volkswagen Polo.jpg', date: '24 oct, 2026', time: '10:38', status: 'review' },
  { id: 'OP-002', title: 'Lectura interrumpida', document: 'Título escaneado.png', date: '24 oct, 2026', time: '10:35', status: 'error' },
  { id: 'OP-001', title: 'Vehículo confirmado', document: 'Título Ford Ranger.pdf', date: '23 oct, 2026', time: '16:20', status: 'ready' },
]
