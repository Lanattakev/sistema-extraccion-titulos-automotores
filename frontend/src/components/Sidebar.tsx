import { Icon } from './Icon'
import { pages } from '../navigation'
import type { NavigationProps, Page } from '../navigation'

export function Sidebar({ activePage, onNavigate }: NavigationProps) {
  function navigationItem(page: Page) {
    const active = activePage === page
    return (
      <button
        key={page}
        type="button"
        className={`nav-item ${active ? 'active' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={() => onNavigate(page)}
      >
        <Icon name={pages[page].icon} />
        <span>{pages[page].label}</span>
        {active && <span className="active-dot" />}
      </button>
    )
  }

  return (
    <aside className="sidebar">
      <button className="brand" type="button" onClick={() => onNavigate('home')} aria-label="Fast Procedure — Inicio">
        <span className="brand-symbol"><Icon name="car" size={36} /></span>
        <span><strong>Fast Procedure<span className="brand-dot">.</span></strong><small>Gestión Vehicular</small></span>
      </button>
      <p className="nav-label">ESPACIO DE TRABAJO</p>
      <nav aria-label="Navegación principal">
        {(['home', 'upload', 'vehicles', 'metrics', 'history'] as const).map(navigationItem)}
      </nav>
      <div className="sidebar-bottom">
        <div className="workspace-note"><span className="status-dot" /> Tu espacio, en orden.<small>Menos tareas. Más posibilidades.</small></div>
        <nav aria-label="Soporte">{(['settings', 'help'] as const).map(navigationItem)}</nav>
        <div className="sidebar-footer">FAST PROCEDURE <span>MVP · 01</span></div>
      </div>
    </aside>
  )
}
