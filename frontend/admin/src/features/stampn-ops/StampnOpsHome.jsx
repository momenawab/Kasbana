import { useState } from 'react'
import { Activity, BellRing, LayoutDashboard, ShieldCheck } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import Dashboard from './Dashboard'
import Alerts from './Alerts'
import Settings from './Settings'

const tabs = [{ key: 'dashboard', label: 'Dashboard', Icon: LayoutDashboard }, { key: 'alerts', label: 'Alerts', Icon: Activity }, { key: 'settings', label: 'Alert & Telegram settings', Icon: BellRing }]
export default function StampnOpsHome() { const { role } = useAuth(); const [tab, setTab] = useState('dashboard'); if (role !== 'SUPER_ADMIN') return <div className="mx-auto max-w-lg rounded-ctl border border-red-500/30 bg-red-500/10 p-6 text-center"><ShieldCheck className="mx-auto text-red-600" size={28} /><h1 className="mt-3 text-lg font-bold text-tx">Super Admin access required</h1><p className="mt-2 text-sm text-tx-2">Stampn Ops is restricted to the platform Owner.</p></div>; return <div className="flex flex-col gap-5"><header><p className="text-sm text-tx-3">Internal platform control room</p><h1 className="font-head text-2xl font-bold text-tx">🛠 Stampn Ops</h1></header><nav className="flex gap-1 overflow-auto border-b border-line">{tabs.map(({ key, label, Icon }) => <button key={key} onClick={() => setTab(key)} className={`flex shrink-0 items-center gap-2 px-3 py-2 text-sm ${tab === key ? 'border-b-2 border-brand font-semibold text-brand' : 'text-tx-3 hover:text-tx'}`}><Icon size={16} />{label}</button>)}</nav>{tab === 'dashboard' && <Dashboard />}{tab === 'alerts' && <Alerts />}{tab === 'settings' && <Settings />}</div> }
