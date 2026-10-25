import type { PersistedDocument } from './documents'

export type ReviewedVehicle = {
  patente: string
  marca: string
  modelo: string
  numero_motor: string
  numero_chasis: string
  anio: number
}

export type VehicleIntake = {
  vehicle: ReviewedVehicle
  archivo_origen: string
  id_interno: string
  fecha_ingreso: string
  requiere_revision: boolean
}

export type VehiclesState = {
  vehicles: VehicleIntake[] | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

export type ConfirmationState = {
  reviewed?: ReviewedVehicle
  pending?: boolean
  savingReview?: boolean
  registered?: Pick<VehicleIntake, 'vehicle' | 'id_interno'>
  dirty?: boolean
  error?: string
}

export type BatchConfirmation = {
  running: boolean
  total: number
  completed: number
  registered: string[]
  failed: string[]
}

export type ConfirmationProps = {
  persistedDocuments: PersistedDocument[]
  documentsLoading: boolean
  documentsError: string | null
  refreshDocuments: () => Promise<void>
  confirmations: Record<string, ConfirmationState>
  batchConfirmation: BatchConfirmation | null
  onMarkReviewed: (documentId: string, fields: ReviewedVehicle) => Promise<void>
  onInvalidateReview: (documentId: string) => void
  onConfirm: (documentId: string) => Promise<void>
  onConfirmSelected: (documentIds: string[]) => Promise<void>
}
