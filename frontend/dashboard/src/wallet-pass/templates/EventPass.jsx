// EventPass — concert / wedding / festival / conference ticket. Header brand,
// a "valid till" style label over the event/guest title, a date·venue info row,
// a barcode, a "scan at entrance" note, and an optional bottom hero image
// (EDM Concert / Mary ♥ Johns references).
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  PassSubtitle,
  FooterImage,
  resolveTheme,
} from '../components'

export default function EventPass({
  theme = 'black',
  brand,
  logo,
  badge,
  label,
  title,
  guestName,
  venue,
  date,
  time,
  info, // optional explicit [{label,value}] row; overrides date/time/venue
  barcodeFormat = 'code128',
  barcodeValue,
  code,
  footerNote,
  heroImage,
  heroPlaceholder,
  ...rest
}) {
  const t = resolveTheme(theme)
  const infoItems = info || [
    { label: 'Date', value: date },
    { label: 'Time', value: time },
    { label: 'Venue', value: venue },
  ]
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={badge} theme={t} />
      <PassTitle label={label} theme={t}>
        {title || guestName}
      </PassTitle>
      <PassInfoRow theme={t} items={infoItems} />
      <div className="flex items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={barcodeValue} code={code} theme={t} />
      </div>
      <PassSubtitle theme={t} align="center">
        {footerNote}
      </PassSubtitle>
      <div className="flex-1" />
      <FooterImage src={heroImage} placeholder={heroPlaceholder} position="bottom" />
    </PassCard>
  )
}
