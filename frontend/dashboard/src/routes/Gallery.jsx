// Dev-only component gallery (spec §2 /__gallery). Renders every design-system
// component so we can verify them in AR+EN at 360px + desktop. Not linked in nav.
import { useState } from 'react'
import { Coffee, Gift, Users } from 'lucide-react'
import Button from '../components/Button'
import { Input, Select, Textarea } from '../components/Field'
import { Toggle, Checkbox } from '../components/Toggle'
import Badge from '../components/Badge'
import Skeleton from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import Banner from '../components/Banner'
import { Modal, Drawer } from '../components/Modal'
import Tabs from '../components/Tabs'
import Stepper from '../components/Stepper'
import Table from '../components/Table'
import KpiTile from '../components/KpiTile'
import ColorPicker from '../components/ColorPicker'
import DateRange from '../components/DateRange'
import QrBlock from '../components/QrBlock'
import WalletPreview from '../components/WalletPreview'
import { ChartLine, ChartBar, ChartDonut } from '../components/Charts'
import { gating } from '../lib/gating'

function Section({ title, children }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 font-head text-lg font-bold text-tx">{title}</h2>
      <div className="flex flex-wrap items-start gap-4 rounded-card border border-line bg-surface p-4">
        {children}
      </div>
    </section>
  )
}

const series = [
  { date: 'Mon', value: 12 },
  { date: 'Tue', value: 19 },
  { date: 'Wed', value: 9 },
  { date: 'Thu', value: 24 },
  { date: 'Fri', value: 31 },
]
const donut = [
  { name: 'Apple', value: 60 },
  { name: 'Google', value: 40 },
]

export default function Gallery() {
  const [modal, setModal] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [tab, setTab] = useState('a')
  const [toggle, setToggle] = useState(true)
  const [check, setCheck] = useState(false)
  const [color, setColor] = useState('#E0A23B')
  const [range, setRange] = useState({ from: '', to: '' })
  const [platform, setPlatform] = useState('APPLE')

  return (
    <div className="mx-auto max-w-4xl p-4">
      <h1 className="mb-6 font-head text-2xl font-bold text-tx">Component Gallery</h1>

      <Section title="Buttons">
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button loading>Loading</Button>
        <Button disabled>Disabled</Button>
      </Section>

      <Section title="Form fields">
        <Input label="Email" name="g-email" placeholder="you@x.com" />
        <Input label="With error" name="g-err" error="Required" />
        <Select label="Plan" name="g-plan" options={[{ value: 's', label: 'Starter' }, { value: 'g', label: 'Growth' }]} />
        <Textarea label="Message" name="g-msg" />
        <Toggle checked={toggle} onChange={setToggle} label="Toggle" />
        <Checkbox checked={check} onChange={setCheck} label="Checkbox" />
        <ColorPicker label="Brand color" value={color} onChange={setColor} />
        <DateRange value={range} onChange={setRange} />
      </Section>

      <Section title="Badges">
        <Badge>Neutral</Badge>
        <Badge tone="violet">Trial</Badge>
        <Badge tone="teal">Active</Badge>
        <Badge tone="fuchsia">Blocked</Badge>
        <Badge tone="success">Reward ready</Badge>
      </Section>

      <Section title="KPI tiles">
        <KpiTile label="Active customers" value={1280} deltaPct={12} icon={Users} tone="violet" />
        <KpiTile label="Stamps this week" value={342} deltaPct={-4} icon={Coffee} tone="teal" />
        <KpiTile label="Rewards" value={56} icon={Gift} tone="fuchsia" />
        <KpiTile label="New joins" value={88} deltaPct={7} tone="slate" />
      </Section>

      <Section title="Charts">
        <div className="w-full rounded-card bg-slate p-4">
          <ChartLine data={series} />
        </div>
        <div className="w-full sm:w-1/2"><ChartBar data={series} /></div>
        <div className="w-full sm:w-1/2"><ChartDonut data={donut} /></div>
      </Section>

      <Section title="Overlays + gating">
        <Button onClick={() => setModal(true)}>Open Modal</Button>
        <Button variant="secondary" onClick={() => setDrawer(true)}>Open Drawer</Button>
        <Button variant="ghost" onClick={() => gating.open('custom_branding')}>Trigger UpgradeDrawer</Button>
        <Modal open={modal} onClose={() => setModal(false)} title="Example modal" footer={<Button onClick={() => setModal(false)}>OK</Button>}>
          <p className="text-tx-2">Modal body content.</p>
        </Modal>
        <Drawer open={drawer} onClose={() => setDrawer(false)} title="Example drawer">
          <p className="text-tx-2">Drawer slides from the inline-end (RTL aware).</p>
        </Drawer>
      </Section>

      <Section title="Tabs + Stepper">
        <Tabs tabs={[{ key: 'a', label: 'One' }, { key: 'b', label: 'Two' }]} active={tab} onChange={setTab} />
        <Stepper steps={['Branding', 'First card', 'Done']} current={1} />
      </Section>

      <Section title="Table">
        <div className="w-full">
          <Table
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'stamps', label: 'Stamps' },
              { key: 'status', label: 'Status', render: (r) => <Badge tone="teal">{r.status}</Badge> },
            ]}
            rows={[
              { id: 1, name: 'Mona', stamps: '3/8', status: 'active' },
              { id: 2, name: 'Ali', stamps: '8/8', status: 'reward' },
            ]}
          />
        </div>
      </Section>

      <Section title="Wallet preview">
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button size="sm" variant={platform === 'APPLE' ? 'primary' : 'ghost'} onClick={() => setPlatform('APPLE')}>Apple</Button>
            <Button size="sm" variant={platform === 'GOOGLE' ? 'primary' : 'ghost'} onClick={() => setPlatform('GOOGLE')}>Google</Button>
          </div>
          <WalletPreview platform={platform} colorBg="#0E1B2A" colorFg="#FFFFFF" merchantName="Cairo Coffee" programName="Coffee club" rewardTitle="Free latte" stampsRequired={8} stampCount={3} />
        </div>
      </Section>

      <Section title="QR + states">
        <QrBlock value="https://app.stampn.net/enroll/demo" />
        <div className="w-48"><Skeleton h={60} rounded="card" /></div>
        <div className="w-full"><Banner tone="violet" action={<Button size="sm">Act</Button>}>Banner notice</Banner></div>
        <div className="w-full">
          <EmptyState icon={Users} title="No customers yet" body="Share your join QR to get started." action={<Button size="sm">Share QR</Button>} />
        </div>
      </Section>
    </div>
  )
}
