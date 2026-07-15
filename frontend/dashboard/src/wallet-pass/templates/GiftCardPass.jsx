// GiftCardPass — balance-led card with an optional full-bleed background
// illustration (the brief's "Background Illustration"). Balance is the hero line;
// the card number and a barcode sit below.
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  resolveTheme,
} from '../components'

export default function GiftCardPass({
  theme = 'purple',
  brand,
  logo,
  badge = 'Gift Card',
  balance,
  cardNumber,
  backgroundImage,
  barcodeValue,
  code,
  barcodeFormat = 'qr',
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} backgroundImage={backgroundImage} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={badge} theme={t} />
      <PassTitle label="Balance" theme={t} size="xl">
        {balance}
      </PassTitle>
      <PassInfoRow theme={t} items={[{ label: 'Card number', value: cardNumber }]} />
      <div className="flex flex-1 items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={barcodeValue} code={code} theme={t} />
      </div>
    </PassCard>
  )
}
