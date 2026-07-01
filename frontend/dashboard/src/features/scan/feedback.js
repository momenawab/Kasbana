// Audible + haptic feedback for the cashier scan flow — a short beep and a
// vibration so staff know a stamp registered without looking at a noisy counter.
// Vibration is Android-only (iOS Safari ignores navigator.vibrate); the beep
// works on both once the AudioContext has been unlocked by a user gesture, which
// `primeFeedback()` arranges on first touch.
let ctx = null

function audio() {
  const Ctor = window.AudioContext || window.webkitAudioContext
  if (!Ctor) return null
  if (!ctx) ctx = new Ctor()
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

function tone(freq, ms) {
  const ac = audio()
  if (!ac) return
  try {
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    const now = ac.currentTime
    gain.gain.setValueAtTime(0.0001, now)
    gain.gain.exponentialRampToValueAtTime(0.2, now + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + ms / 1000)
    osc.connect(gain).connect(ac.destination)
    osc.start(now)
    osc.stop(now + ms / 1000)
  } catch {
    // audio unavailable — silently skip
  }
}

function buzz(pattern) {
  try {
    navigator.vibrate?.(pattern)
  } catch {
    // no vibration support
  }
}

// iOS/Chrome require the AudioContext to be resumed inside a user gesture; call
// once on mount so the first scan beep can actually play. Returns a cleanup fn.
export function primeFeedback() {
  const unlock = () => audio()
  window.addEventListener('pointerdown', unlock, { once: true })
  return () => window.removeEventListener('pointerdown', unlock)
}

export function cueScan() {
  tone(880, 100)
  buzz(40)
}

export function cueSuccess() {
  tone(1040, 130)
  buzz(60)
}

export function cueError() {
  tone(300, 200)
  buzz([40, 60, 40])
}
