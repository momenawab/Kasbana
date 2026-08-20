// SpecialOccasionPass — holiday-themed offer (Valentine, Mother's Day, Eid,
// Ramadan, Christmas…): holiday title over the offer, validity row, a QR, and
// optional themed artwork as a bottom image or full-bleed background
// (Café Delights references).
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  FooterImage,
  resolveTheme,
} from '../components'

export default function SpecialOccasionPass({
  theme = 'pink',
  brand,
  logo,
  holidayTitle,
  offer,
  validOn,
  validAt,
  expiration,
  info, // optional explicit [{label,value}] row; overrides valid-on/valid-at
  qr,
  code,
  barcodeFormat = 'qr',
  artwork,
  artworkPlaceholder,
  artworkMode = 'footer', // 'footer' image band | 'background' full-bleed
  ...rest
}) {
  const t = resolveTheme(theme)
  const background = artworkMode === 'background' ? artwork : undefined
  const infoItems = info || [
    { label: 'Valid on', value: validOn || expiration },
    { label: 'Valid at', value: validAt },
  ]
  return (
    <PassCard theme={t} backgroundImage={background} {...rest}>
      <PassHeader logo={logo} brand={brand} theme={t} />
      <PassTitle label={holidayTitle} theme={t} size="xl">
        {offer}
      </PassTitle>
      <PassInfoRow theme={t} items={infoItems} />
      <div className="flex items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={qr} code={code} theme={t} />
      </div>
      <div className="flex-1" />
      {artworkMode === 'footer' && (
        <FooterImage src={artwork} placeholder={artworkPlaceholder} position="bottom" />
      )}
    </PassCard>
  )
}
