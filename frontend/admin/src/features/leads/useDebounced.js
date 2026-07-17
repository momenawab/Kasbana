import { useEffect, useRef, useState } from 'react'

// Return `value` after it has stopped changing for `delay` ms.
//
// Used for the things that hit the API on every keystroke — the table's search
// box and the Add Lead duplicate probe. Without it, typing an eleven-digit phone
// number is eleven requests, ten of which are already stale when they land.
//
// Objects are compared by their JSON, not by identity: callers pass a fresh
// object literal every render, so an identity check would never settle.
export function useDebounced(value, delay = 300) {
  const [settled, setSettled] = useState(value)
  const serialized = JSON.stringify(value)
  const latest = useRef(value)
  latest.current = value

  useEffect(() => {
    const t = setTimeout(() => setSettled(latest.current), delay)
    return () => clearTimeout(t)
  }, [serialized, delay])

  return settled
}
