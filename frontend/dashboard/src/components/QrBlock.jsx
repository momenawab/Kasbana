import { useRef, useEffect } from 'react'
import { QRCodeCanvas } from 'qrcode.react'
import { Download } from 'lucide-react'
import Button from './Button'

// QrBlock (spec §10) — renders a QR for `value` and downloads it as PNG.
// Colors default to the brand ink/white; the enroll-theme editor passes the
// merchant's chosen QR colors for a live preview.
//
// `moduleStyle` ('square' | 'rounded' | 'dots'): qrcode.react only draws square
// modules, so for the styled shapes we render an off-screen QRCodeCanvas, read
// back its module grid, and repaint it as rounded rects / dots on our own
// canvas. That keeps a single (zero-dependency) code path and makes the
// downloaded PNG match the on-screen shape. The three finder "eyes" stay solid
// so the code remains reliably scannable.

// Threshold a pixel to dark/light by luminance (QR fg must be dark to scan).
function darkAt(data, w, x, y) {
  const i = (y * w + x) * 4
  const lum = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114
  return data[i + 3] > 10 && lum < 128
}

// Recover the N×N module grid from a rendered (margin-less) QR canvas by
// measuring the top-left finder pattern, which is always 7 modules wide.
function readMatrix(src) {
  const w = src.width
  const data = src.getContext('2d').getImageData(0, 0, w, w).data
  const y = Math.max(1, Math.floor(w * 0.01)) // a hair inside the first module row
  let run = 0
  while (run < w && darkAt(data, w, run, y)) run++
  if (run < 7) return null // no detectable finder → let caller fall back to square
  const module = run / 7
  const n = Math.round(w / module)
  const cells = []
  for (let r = 0; r < n; r++) {
    const row = []
    for (let c = 0; c < n; c++) {
      row.push(darkAt(data, w, Math.floor((c + 0.5) * module), Math.floor((r + 0.5) * module)))
    }
    cells.push(row)
  }
  return { cells, n }
}

// A finder "eye" occupies the three 7×7 corners; keep those solid for scanning.
function inEye(r, c, n) {
  const tl = r < 7 && c < 7
  const tr = r < 7 && c >= n - 7
  const bl = r >= n - 7 && c < 7
  return tl || tr || bl
}

function roundedRect(ctx, x, y, s, radius) {
  const rad = Math.min(radius, s / 2)
  ctx.beginPath()
  ctx.moveTo(x + rad, y)
  ctx.arcTo(x + s, y, x + s, y + s, rad)
  ctx.arcTo(x + s, y + s, x, y + s, rad)
  ctx.arcTo(x, y + s, x, y, rad)
  ctx.arcTo(x, y, x + s, y, rad)
  ctx.fill()
}

function paintStyled(src, out, { fgColor, bgColor, moduleStyle }) {
  const matrix = readMatrix(src)
  const ctx = out.getContext('2d')
  if (!matrix) {
    // Fallback: mirror the plain square render so we never show a blank canvas.
    out.width = src.width
    out.height = src.height
    ctx.drawImage(src, 0, 0)
    return
  }
  const { cells, n } = matrix
  const cell = 12 // internal px per module → crisp PNG; CSS scales it to `size`
  const px = n * cell
  out.width = px
  out.height = px
  ctx.fillStyle = bgColor
  ctx.fillRect(0, 0, px, px)
  ctx.fillStyle = fgColor
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      if (!cells[r][c]) continue
      const x = c * cell
      const y = r * cell
      if (moduleStyle === 'dots' && !inEye(r, c, n)) {
        ctx.beginPath()
        ctx.arc(x + cell / 2, y + cell / 2, cell * 0.42, 0, Math.PI * 2)
        ctx.fill()
      } else if (moduleStyle === 'rounded') {
        roundedRect(ctx, x, y, cell, cell * 0.3)
      } else {
        ctx.fillRect(x, y, cell, cell)
      }
    }
  }
}

export default function QrBlock({
  value,
  size = 220,
  downloadName = 'stampn-qr',
  fgColor = '#0E1B2A',
  bgColor = '#FFFFFF',
  moduleStyle = 'square',
}) {
  const ref = useRef(null)
  const hiddenRef = useRef(null)
  const outRef = useRef(null)
  const styled = moduleStyle === 'rounded' || moduleStyle === 'dots'

  useEffect(() => {
    if (!styled) return
    const src = hiddenRef.current?.querySelector('canvas')
    const out = outRef.current
    if (src && out) paintStyled(src, out, { fgColor, bgColor, moduleStyle })
  }, [value, size, fgColor, bgColor, moduleStyle, styled])

  function downloadPng() {
    const canvas = styled ? outRef.current : ref.current?.querySelector('canvas')
    if (!canvas) return
    const a = document.createElement('a')
    a.href = canvas.toDataURL('image/png')
    a.download = `${downloadName}.png`
    a.click()
  }

  return (
    <div className="inline-flex flex-col items-center gap-3">
      <div className="rounded-card bg-white p-4 shadow-bold">
        {styled ? (
          <>
            {/* Off-screen square render we read the module grid from. */}
            <div
              ref={hiddenRef}
              aria-hidden
              style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden', opacity: 0 }}
            >
              <QRCodeCanvas value={value || ''} size={size} fgColor={fgColor} bgColor={bgColor} />
            </div>
            <canvas ref={outRef} style={{ width: size, height: size }} />
          </>
        ) : (
          <div ref={ref}>
            <QRCodeCanvas value={value || ''} size={size} fgColor={fgColor} bgColor={bgColor} />
          </div>
        )}
      </div>
      <Button variant="ghost" size="sm" iconStart={Download} onClick={downloadPng}>
        PNG
      </Button>
    </div>
  )
}
