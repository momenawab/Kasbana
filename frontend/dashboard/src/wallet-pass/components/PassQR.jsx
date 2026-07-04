// PassQR — a real, scannable QR rendered on the white panel Apple Wallet uses
// for machine-readable codes. Fades in on mount. `value` is the encoded payload;
// `code` is the optional human-readable string shown beneath it.
import { QRCodeSVG } from 'qrcode.react'

export default function PassQR({ value = '', size = 116, code, panel = true, theme }) {
  const qr = (
    <QRCodeSVG value={value || ' '} size={size} level="M" includeMargin={false} fgColor="#111111" />
  )
  if (!panel) return <div className="pass-qr-fade">{qr}</div>
  return (
    <div className="flex flex-col items-center">
      <div className="pass-qr-fade rounded-2xl bg-white p-3 shadow-sm">{qr}</div>
      {code && (
        <span
          className="mt-2 font-mono text-[11px] tracking-widest"
          style={{ color: theme?.sub || 'rgba(255,255,255,0.9)' }}
        >
          {code}
        </span>
      )}
    </div>
  )
}
