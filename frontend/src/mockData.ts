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
