import { useRef } from 'react'
import { QRCodeCanvas } from 'qrcode.react'
import { Download } from 'lucide-react'
import Button from './Button'

// QrBlock (spec §10) — renders a QR for `value` and downloads it as PNG.
// Colors default to the brand ink/white; the enroll-theme editor passes the
// merchant's chosen QR colors for a live preview.
export default function QrBlock({
  value,
  size = 220,
  downloadName = 'stampn-qr',
  fgColor = '#0E1B2A',
  bgColor = '#FFFFFF',
}) {
  const ref = useRef(null)

  function downloadPng() {
    const canvas = ref.current?.querySelector('canvas')
    if (!canvas) return
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `${downloadName}.png`
    a.click()
  }

  return (
    <div className="inline-flex flex-col items-center gap-3">
      <div ref={ref} className="rounded-card bg-white p-4 shadow-bold">
        <QRCodeCanvas value={value || ''} size={size} fgColor={fgColor} bgColor={bgColor} />
      </div>
      <Button variant="ghost" size="sm" iconStart={Download} onClick={downloadPng}>
        PNG
      </Button>
    </div>
  )
}
