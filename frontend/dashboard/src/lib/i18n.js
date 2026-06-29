// i18next init. `ar` is default + source of truth; `en` mirrors its keys.
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import ar from '../locales/ar.json'
import en from '../locales/en.json'

export const LANG_KEY = 'kasbana_lang'

const saved = localStorage.getItem(LANG_KEY)
const initialLang = saved === 'en' || saved === 'ar' ? saved : 'ar'

i18n.use(initReactI18next).init({
  resources: { ar: { translation: ar }, en: { translation: en } },
  lng: initialLang,
  fallbackLng: 'ar',
  interpolation: { escapeValue: false },
})

/** Apply <html lang/dir> for the given language. */
export function applyDir(lang) {
  document.documentElement.lang = lang
  document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
}

/** Switch language: persist, update i18next, flip dir. */
export function setLang(lang) {
  localStorage.setItem(LANG_KEY, lang)
  i18n.changeLanguage(lang)
  applyDir(lang)
}

applyDir(initialLang)

export default i18n
