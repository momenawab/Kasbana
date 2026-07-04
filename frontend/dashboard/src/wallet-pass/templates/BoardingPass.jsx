// BoardingPass — deliberately minimal (the brief's "minimal style"): airline
// header, route over passenger name, a flight/seat/gate row and a boarding-time
// row, then a QR (Spirit Airlines reference). No hero image.
import {
  PassCard,
  PassHeader,
  PassTitle,
  PassInfoRow,
  PassBarcode,
  resolveTheme,
} from '../components'

export default function BoardingPass({
  theme = 'yellow',
  brand,
  logo,
  badge = 'Boarding',
  route,
  passenger,
  flightNo,
  seat,
  gate,
  boardingTime,
  date,
  qr,
  code,
  barcodeFormat = 'qr',
  ...rest
}) {
  const t = resolveTheme(theme)
  return (
    <PassCard theme={t} {...rest}>
      <PassHeader logo={logo} brand={brand} badge={badge} theme={t} />
      <PassTitle label={route} theme={t}>
        {passenger}
      </PassTitle>
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Flight', value: flightNo, align: 'start' },
          { label: 'Seat', value: seat, align: 'start' },
          { label: 'Gate', value: gate, align: 'end' },
        ]}
      />
      <PassInfoRow
        theme={t}
        items={[
          { label: 'Boarding', value: boardingTime, align: 'start' },
          { label: 'Date', value: date, align: 'end' },
        ]}
      />
      <div className="flex flex-1 items-center justify-center py-1">
        <PassBarcode format={barcodeFormat} value={qr} code={code} theme={t} />
      </div>
    </PassCard>
  )
}
