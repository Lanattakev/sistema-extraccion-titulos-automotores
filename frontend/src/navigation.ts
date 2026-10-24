import type { IconName } from './components/Icon'

export const pages = {
  home: { label: 'Inicio', icon: 'home', title: 'Gestión inteligente de títulos', description: 'Extraé la información de tus documentos y organizá el registro vehicular. Todo en un lugar. Con vos al mando.' },
  upload: { label: 'Cargar títulos', icon: 'upload', title: 'Un título, un nuevo registro', description: 'Un espacio para cargar, revisar y organizar tus documentos vehiculares.' },
  vehicles: { label: 'Vehículos', icon: 'car', title: 'Tu registro vehicular', description: 'La información de cada vehículo, clara y a mano.' },
  metrics: { label: 'Métricas', icon: 'chart', title: 'Una mirada a tu actividad', description: 'Indicadores simples para entender el movimiento de tu espacio.' },
  history: { label: 'Historial', icon: 'history', title: 'Cada paso, en su lugar', description: 'Consultá las operaciones recientes y el estado de tus documentos.' },
  settings: { label: 'Configuración', icon: 'settings', title: 'Un espacio a tu medida', description: 'Ajustá la apariencia y conocé las preferencias de tu espacio de trabajo.' },
  help: { label: 'Ayuda', icon: 'help', title: 'De tu título al registro', description: 'Tres pasos simples, con una revisión humana en el centro.' },
} satisfies Record<string, { label: string; icon: IconName; title: string; description: string }>

export type Page = keyof typeof pages
export type NavigationProps = { activePage: Page; onNavigate: (page: Page) => void }
