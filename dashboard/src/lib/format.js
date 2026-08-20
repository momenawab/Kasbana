// Formatting helpers (Direction-C: Arabic-Indic digits + EGP money + relative time).
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/ar'

dayjs.extend(relativeTime)

const AR_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩']

/** Map Western digits in a string to Arabic-Indic when lang is 'ar'. */
export function arDigits(value, lang) {
  const s = String(value ?? '')
  if (lang !== 'ar') return s
  return s.replace(/[0-9]/g, (d) => AR_DIGITS[Number(d)])
}

/** EGP money in major units, e.g. 199 -> "199 ج.م" / "١٩٩ ج.م". */
export function money(amount, lang) {
  const n = Number(amount ?? 0)
  const formatted = arDigits(n.toLocaleString('en-US'), lang)
  return lang === 'ar' ? `${formatted} ج.م` : `EGP ${formatted}`
}

/** Relative time ("3 hours ago") localized. */
export function fromNow(date, lang) {
  return dayjs(date)
    .locale(lang === 'ar' ? 'ar' : 'en')
    .fromNow()
}

/** Whole days remaining until a date (for the trial countdown). */
export function daysUntil(date) {
  return Math.max(0, dayjs(date).diff(dayjs(), 'day'))
}

/** Localized absolute date, e.g. "5 Aug 2026" / "٥ أغسطس ٢٠٢٦". */
export function fmtDate(date, lang) {
  if (!date) return ''
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-EG' : 'en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(date))
}
