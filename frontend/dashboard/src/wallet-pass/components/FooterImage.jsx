// FooterImage — an optional hero image bleeding to the pass edges (bottom by
// default, as in the Event and Special-Occasion references; also usable as a top
// hero). PassCard has `overflow: hidden`, so the image corners are clipped to the
// pass radius. Renders nothing without a src.

export default function FooterImage({ src, position = 'bottom', height = 132 }) {
  if (!src) return null
  const edge =
    position === 'bottom'
      ? '-mx-4 -mb-4 mt-3'
      : position === 'top'
        ? '-mx-4 -mt-4 mb-3'
        : '-mx-4'
  return (
    <div className={edge} style={{ height }}>
      <img src={src} alt="" className="h-full w-full object-cover" />
    </div>
  )
}
