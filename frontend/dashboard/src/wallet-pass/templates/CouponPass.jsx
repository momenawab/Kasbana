// CouponPass — a discount offer with the discount as the hero line, validity
// details, and a barcode. Accent-driven, matching the brief's "Accent Color".
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  PassSubtitle,
  resolveTheme,
} from '../components'

export default function CouponPass({
  theme = 'red',
  brand,
  logo,
  badge = 'Coupon',
  offer,
  discount,
  expiry,
  validAt,
  footerNote,
  barcodeValue,
  code,
  barcodeFormat = 'code128',
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={badge} theme={t} />
      <PassTitle label={offer} theme={t} size="xl">
        {discount}
      </PassTitle>
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Valid until', value: expiry },
          { label: 'Valid at', value: validAt },
        ]}
      />
      <div className="flex flex-1 items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={barcodeValue} code={code} theme={t} />
      </div>
      <PassSubtitle theme={t} align="center">
        {footerNote}
      </PassSubtitle>
    </PassCard>
  )
}
