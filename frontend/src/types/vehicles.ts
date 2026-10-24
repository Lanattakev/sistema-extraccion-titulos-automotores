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
  registered?: VehicleIntake
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
  confirmations: Record<string, ConfirmationState>
  batchConfirmation: BatchConfirmation | null
  onMarkReviewed: (documentId: string, fields: ReviewedVehicle) => void
  onInvalidateReview: (documentId: string) => void
  onConfirm: (documentId: string) => Promise<void>
  onConfirmSelected: (documentIds: string[]) => Promise<void>
}
