// MembershipPass — business membership with a tier badge, member name + ID,
// expiry, and a barcode (Code128 by default, as most membership scanners use 1D).
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  resolveTheme,
} from '../components'

export default function MembershipPass({
  theme = 'black',
  brand,
  logo,
  tier,
  label = 'Member',
  memberName,
  memberId,
  expiry,
  barcodeValue,
  code,
  barcodeFormat = 'code128',
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={tier} theme={t} />
      <PassTitle label={label} theme={t}>
        {memberName}
      </PassTitle>
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Member ID', value: memberId },
          { label: 'Expiry', value: expiry },
        ]}
      />
      <div className="flex flex-1 items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={barcodeValue} code={code} theme={t} />
      </div>
    </PassCard>
  )
}
