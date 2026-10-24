import { Icon } from './Icon'

export type Theme = 'light' | 'dark'
export type ThemeProps = { theme: Theme; onThemeChange: (theme: Theme) => void }

export function ThemeSwitch({ theme, onThemeChange }: ThemeProps) {
  return (
    <div className="theme-switch" role="group" aria-label="Apariencia">
      {(['light', 'dark'] as const).map((mode) => (
        <button
          key={mode}
          type="button"
          aria-label={mode === 'light' ? 'Tema claro' : 'Tema oscuro'}
          aria-pressed={theme === mode}
          onClick={() => onThemeChange(mode)}
        >
          <Icon name={mode === 'light' ? 'sun' : 'moon'} size={18} />
        </button>
      ))}
    </div>
  )
}
