// InvitationPass — "you are invited" card: title over guest/date/time/location,
// a barcode, and a bottom hero image (Ria's Birthday reference).
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  FooterImage,
  resolveTheme,
} from '../components'

export default function InvitationPass({
  theme = 'yellow',
  brand = 'You are invited!',
  logo,
  label = 'Join us to celebrate',
  title,
  guest,
  date,
  time,
  location,
  barcodeValue,
  code,
  barcodeFormat = 'code128',
  heroImage,
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} theme={t} />
      <PassTitle label={label} theme={t}>
        {title}
      </PassTitle>
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Guest', value: guest },
          { label: 'Time', value: time },
        ]}
      />
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Date', value: date },
          { label: 'Location', value: location },
        ]}
      />
      <div className="flex items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={barcodeValue} code={code} theme={t} />
      </div>
      <div className="flex-1" />
      <FooterImage src={heroImage} position="bottom" />
    </PassCard>
  )
}
