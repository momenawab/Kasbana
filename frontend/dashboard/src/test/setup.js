import '@testing-library/jest-dom'

// jsdom has no ResizeObserver, which recharts' <ResponsiveContainer> constructs on
// mount. Charts get zero width here (layout is never computed), so tests assert on
// the surrounding markup, not the SVG — this just keeps the mount from throwing.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}
