import { pages } from '../navigation'
import type { Page } from '../navigation'
import { ThemeSwitch } from './ThemeSwitch'
import type { ThemeProps } from './ThemeSwitch'

export function Header({ activePage, theme, onThemeChange }: ThemeProps & { activePage: Page }) {
  return (
    <header className="topbar">
      <div className="breadcrumb">Espacio de trabajo<span>/</span><strong>{pages[activePage].label}</strong></div>
      <div className="topbar-actions">
        <ThemeSwitch theme={theme} onThemeChange={onThemeChange} />
        <span className="header-divider" />
        <div className="user"><span className="avatar">OP</span><span>Operador<small>Mi espacio de trabajo</small></span></div>
      </div>
    </header>
  )
}
