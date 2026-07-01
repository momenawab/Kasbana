import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-amber text-ink hover:bg-amber-d',
  secondary: 'bg-ink text-white hover:bg-ink-2',
  ghost: 'bg-transparent text-tx hover:bg-paper border border-line',
  danger: 'bg-danger text-white hover:opacity-90',
}
const SIZES = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2', lg: 'px-5 py-3 text-lg' }

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  iconStart: Icon,
  type = 'button',
  className = '',
  children,
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-ctl font-semibold transition disabled:opacity-60 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : Icon ? <Icon size={16} /> : null}
      {children}
    </button>
  )
}
