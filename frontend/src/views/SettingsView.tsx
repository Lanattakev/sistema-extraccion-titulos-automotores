import { ThemeSwitch } from '../components/ThemeSwitch'
import type { ThemeProps } from '../components/ThemeSwitch'

export function SettingsView({ theme, onThemeChange }: ThemeProps) {
  return (
    <div className="view-stack settings-content">
      <section className="panel" aria-labelledby="appearance-title">
        <div className="panel-heading"><div><h2 id="appearance-title">Apariencia</h2><p>Elegí cómo querés ver tu espacio de trabajo.</p></div></div>
        <div className="setting-row"><div><h3>Tema de la aplicación</h3><p>Se aplica a todas las vistas durante esta sesión.</p></div><div className="setting-theme"><span>{theme === 'light' ? 'Claro' : 'Oscuro'}</span><ThemeSwitch theme={theme} onThemeChange={onThemeChange} /></div></div>
      </section>
      <section className="panel" aria-labelledby="preferences-title">
        <div className="panel-heading"><div><h2 id="preferences-title">Preferencias del espacio</h2><p>Opciones visuales de demostración.</p></div><span className="demo-label">Vista previa</span></div>
        <div className="setting-row"><div><h3>Idioma</h3><p>Idioma de la interfaz.</p></div><span className="setting-value">Español (Argentina)</span></div>
        <div className="setting-row"><div><h3>Revisión antes del registro</h3><p>La información se revisa antes de confirmar un vehículo.</p></div><span className="setting-value">Siempre activa</span></div>
        <div className="setting-row"><div><h3>Notificaciones de actividad</h3><p>Disponible en una próxima etapa.</p></div><input type="checkbox" role="switch" aria-label="Notificaciones de actividad (próximamente)" disabled /></div>
      </section>
    </div>
  )
}
