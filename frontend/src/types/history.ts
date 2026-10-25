export type HistoryEvent = {
  id_evento: string
  id_documento: string
  tipo_evento: 'documento_cargado' | 'documento_revisado' | 'documento_registrado'
  fecha_evento: string
  nombre_original: string
}

export type HistoryState = {
  events: HistoryEvent[] | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}
