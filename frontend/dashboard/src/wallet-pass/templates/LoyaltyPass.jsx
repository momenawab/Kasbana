// LoyaltyPass — brand offer + membership details + a QR and the reward stamp
// strip (Buns & Bros / Cafe Muse references). The reward row's final chip lights
// up once the card is complete.
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  RewardStampRow,
  resolveTheme,
} from '../components'

export default function LoyaltyPass({
  theme = 'red',
  brand,
  logo,
  badge,
  offer,
  title,
  customerName,
  memberId,
  expiration,
  qr,
  code,
  barcodeFormat = 'qr',
  rewardProgress = 0,
  rewardTarget = 5,
  rewardIcon,
  stampEmoji, // food/drink emoji shown in each stamp (e.g. 🍔 / 🍩 / ☕)
  rewardEmoji,
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={badge} theme={t} />
      <PassTitle label={offer} theme={t}>
        {title}
      </PassTitle>
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Name', value: customerName },
          { label: 'Member ID', value: memberId },
          { label: 'Expires', value: expiration },
        ]}
      />
      <div className="flex flex-1 items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={qr} code={code} theme={t} />
      </div>
      <RewardStampRow
        theme={t}
        progress={rewardProgress}
        target={rewardTarget}
        rewardIcon={rewardIcon}
        emoji={stampEmoji}
        rewardEmoji={rewardEmoji}
      />
    </PassCard>
  )
}
