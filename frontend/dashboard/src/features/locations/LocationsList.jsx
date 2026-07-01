// Locations (spec §14) — table + add/edit modal. "Add" gated at max_locations.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, MapPin } from 'lucide-react'
import { useLocations, useSaveLocation } from './api'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import { normalizeError } from '../../lib/api'
import Table from '../../components/Table'
import Button from '../../components/Button'
import EmptyState from '../../components/EmptyState'
import { Modal } from '../../components/Modal'
import { Input } from '../../components/Field'

const EMPTY = { name: '', address: '', lat: '', lng: '' }

export default function LocationsList() {
  const { t } = useTranslation()
  const { atLimit, requireRoom } = usePlan()
  const toast = useToast()
  const { data: locations = [], isLoading } = useLocations()
  const save = useSaveLocation()

  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY)

  function openNew() {
    if (!requireRoom('max_locations')) return
    setForm(EMPTY)
    setOpen(true)
  }

  function openEdit(loc) {
    setForm({ id: loc.id, name: loc.name, address: loc.address || '', lat: loc.lat ?? '', lng: loc.lng ?? '' })
    setOpen(true)
  }

  async function submit() {
    if (!form.name.trim() || !form.address.trim()) {
      toast.error(t('locations.required'))
      return
    }
    try {
      await save.mutateAsync({
        id: form.id,
        name: form.name,
        address: form.address,
        lat: form.lat === '' ? null : Number(form.lat),
        lng: form.lng === '' ? null : Number(form.lng),
      })
      toast.success(t('locations.saved'))
      setOpen(false)
    } catch (err) {
      const { code, message } = normalizeError(err)
      toast.error(code === 'PLAN_LIMIT' ? t('locations.limit') : message)
    }
  }

  const columns = [
    { key: 'name', label: t('locations.name') },
    { key: 'address', label: t('locations.address') },
    { key: 'staff_count', label: t('locations.staff'), render: (r) => <span className="font-num">{r.staff_count ?? 0}</span> },
    { key: 'stamps_issued', label: t('locations.stamps'), render: (r) => <span className="font-num">{r.stamps_issued ?? 0}</span> },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-ink">{t('locations.title')}</h1>
        <Button iconStart={Plus} onClick={openNew} disabled={atLimit('max_locations')}>
          {t('locations.add')}
        </Button>
      </div>

      <Table
        columns={columns}
        rows={locations}
        loading={isLoading}
        onRowClick={openEdit}
        emptyState={
          <EmptyState
            icon={MapPin}
            title={t('locations.emptyTitle')}
            body={t('locations.emptyBody')}
            action={<Button iconStart={Plus} onClick={openNew}>{t('locations.add')}</Button>}
          />
        }
      />

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={form.id ? t('locations.editTitle') : t('locations.addTitle')}
        footer={
          <Button onClick={submit} loading={save.isPending} className="w-full">
            {t('locations.save')}
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <Input name="name" label={t('locations.name')} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input name="address" label={t('locations.address')} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <Input name="lat" label="Lat" type="number" value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} />
            <Input name="lng" label="Lng" type="number" value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
