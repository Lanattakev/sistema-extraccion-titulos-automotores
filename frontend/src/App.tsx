import { useRef, useState } from 'react'
import { Header } from './components/Header'
import { PageHeading } from './components/PageHeading'
import { Sidebar } from './components/Sidebar'
import type { Theme } from './components/ThemeSwitch'
import { pages } from './navigation'
import type { Page } from './navigation'
import { HelpView } from './views/HelpView'
import { HistoryView } from './views/HistoryView'
import { HomeView } from './views/HomeView'
import { MetricsView } from './views/MetricsView'
import { SettingsView } from './views/SettingsView'
import { UploadView } from './views/UploadView'
import { VehiclesView } from './views/VehiclesView'
import './App.css'

function App() {
  const [theme, setTheme] = useState<Theme>('light')
  const [activePage, setActivePage] = useState<Page>('home')
  const mainRef = useRef<HTMLElement>(null)

  function navigate(page: Page) {
    setActivePage(page)
    document.title = `${pages[page].label} — Fast Procedure · Gestión Vehicular`
    // Esperar al render permite llevar el foco al título de la nueva vista.
    requestAnimationFrame(() => {
      mainRef.current?.querySelector<HTMLElement>('h1')?.focus({ preventScroll: true })
      window.scrollTo({ top: 0, behavior: 'instant' })
    })
  }

  const views = {
    home: <HomeView />,
    upload: <UploadView />,
    vehicles: <VehiclesView />,
    metrics: <MetricsView />,
    history: <HistoryView />,
    settings: <SettingsView theme={theme} onThemeChange={setTheme} />,
    help: <HelpView onNavigate={navigate} />,
  }

  return (
    <div className="app-shell" data-theme={theme}>
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      <Sidebar activePage={activePage} onNavigate={navigate} />
      <div className="main-shell">
        <Header activePage={activePage} theme={theme} onThemeChange={setTheme} />
        <main id="main-content" ref={mainRef} aria-labelledby="page-title">
          <PageHeading title={pages[activePage].title} description={pages[activePage].description} />
          {views[activePage]}
          <footer className="page-footer"><span>Fast Procedure <span className="footer-dot">·</span> Gestión con claridad.</span><span>Una forma más simple de avanzar.</span></footer>
        </main>
      </div>
    </div>
  )
}

export default App
