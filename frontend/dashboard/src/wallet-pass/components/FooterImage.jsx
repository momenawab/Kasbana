// FooterImage — an optional hero image bleeding to the pass edges (bottom by
// default, as in the Event and Special-Occasion references; also usable as a top
// hero). PassCard has `overflow: hidden`, so the image corners are clipped to the
// pass radius. Renders nothing without a src.

export default function FooterImage({ src, placeholder, position = 'bottom', height = 132 }) {
  if (!src && !placeholder) return null
  const edge =
    position === 'bottom'
      ? '-mx-4 -mb-4 mt-3'
      : position === 'top'
        ? '-mx-4 -mt-4 mb-3'
        : '-mx-4'
  // `placeholder` = { gradient, emoji } — stands in for the merchant's uploaded
  // photo in previews/galleries, so the layout's image band is visible without a
  // real asset. A real `src` always takes precedence.
  return (
    <div className={edge} style={{ height }}>
      {src ? (
        <img src={src} alt="" className="h-full w-full object-cover" />
      ) : (
        <div
          className="flex h-full w-full items-center justify-center"
          style={{ background: placeholder.gradient }}
        >
          {placeholder.emoji && (
            <span style={{ fontSize: 40 }} className="opacity-90">
              {placeholder.emoji}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
