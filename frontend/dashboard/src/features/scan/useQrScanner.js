// Live QR scanning off a device camera. Prefers the native BarcodeDetector
// (Chrome/Android); falls back to jsQR per-frame for iOS/Safari, where most
// tills run. Driven by an `active` flag so the camera is released the moment
// the screen shows a result or unmounts.
import { useEffect, useRef, useState } from 'react'
import jsQR from 'jsqr'

function readFrame(video, canvas) {
  const w = video.videoWidth
  const h = video.videoHeight
  if (!w || !h) return null
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  ctx.drawImage(video, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  return jsQR(data, w, h, { inversionAttempts: 'dontInvert' })?.data || null
}

export function useQrScanner({ active, onResult }) {
  const videoRef = useRef(null)
  const onResultRef = useRef(onResult)
  onResultRef.current = onResult
  // idle | starting | scanning | denied | unsupported | error
  const [status, setStatus] = useState('idle')

  useEffect(() => {
    if (!active) return
    const video = videoRef.current
    let stream = null
    let raf = 0
    let stopped = false
    let detector = null
    const canvas = document.createElement('canvas')

    async function tick() {
      if (stopped) return
      if (video && video.readyState >= 2) {
        let code = null
        try {
          if (detector) {
            const hits = await detector.detect(video)
            code = hits[0]?.rawValue || null
          } else {
            code = readFrame(video, canvas)
          }
        } catch {
          // transient frame/decode error — keep scanning
        }
        if (code) {
          onResultRef.current(code)
          return
        }
      }
      raf = requestAnimationFrame(tick)
    }

    async function run() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('unsupported')
        return
      }
      setStatus('starting')
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
          audio: false,
        })
        if (stopped || !video) {
          stream.getTracks().forEach((tk) => tk.stop())
          return
        }
        video.srcObject = stream
        video.setAttribute('playsinline', 'true')
        await video.play()
        if ('BarcodeDetector' in window) {
          try {
            detector = new window.BarcodeDetector({ formats: ['qr_code'] })
          } catch {
            detector = null
          }
        }
        setStatus('scanning')
        tick()
      } catch (err) {
        setStatus(err?.name === 'NotAllowedError' ? 'denied' : 'error')
      }
    }

    run()
    return () => {
      stopped = true
      cancelAnimationFrame(raf)
      if (stream) stream.getTracks().forEach((tk) => tk.stop())
      if (video) video.srcObject = null
      setStatus('idle')
    }
  }, [active])

  return { videoRef, status }
}
