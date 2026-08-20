// Light/dark theme controller. The choice is remembered in localStorage and
// applied by toggling `.dark` on <html>; the actual colors live as CSS
// variables in index.css. Default is light (dark is opt-in) per product choice.
import { useSyncExternalStore } from 'react'

export const THEME_KEY = 'stampn_theme'

function saved() {
  const v = localStorage.getItem(THEME_KEY)
  return v === 'light' || v === 'dark' ? v : null
}

/** Resolve the theme to apply on boot: saved choice, else light. */
export function initialTheme() {
  return saved() ?? 'light'
}

let current = initialTheme()
const listeners = new Set()

/** Apply a theme to <html> and the browser UI (address bar) without persisting. */
export function applyTheme(theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0F0D18' : '#F5F4FA')
}

export function getTheme() {
  return current
}

/** Persist + apply a theme and notify subscribers. */
export function setTheme(theme) {
  current = theme === 'dark' ? 'dark' : 'light'
  localStorage.setItem(THEME_KEY, current)
  applyTheme(current)
  listeners.forEach((l) => l())
}

export function toggleTheme() {
  setTheme(current === 'dark' ? 'light' : 'dark')
}

function subscribe(cb) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

/** React hook: current theme, re-renders on change. */
export function useTheme() {
  return useSyncExternalStore(subscribe, getTheme, getTheme)
}

// Apply immediately on module load so there's no light-flash before React.
applyTheme(current)
