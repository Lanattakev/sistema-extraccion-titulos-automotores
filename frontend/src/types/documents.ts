export type BatchDocumentResult = {
  id_documento?: string | null
  nombre_original?: string | null
  patente?: string | null
  marca?: string | null
  modelo?: string | null
  numero_motor?: string | null
  numero_chasis?: string | null
  anio?: number | null
  requiere_revision?: boolean
  fallo?: boolean
  error?: string | null
}

export type PersistedDocument = BatchDocumentResult & {
  id_documento: string
  nombre_original: string
  estado: 'pendiente' | 'revisado' | 'registrado'
  id_interno: string | null
}
