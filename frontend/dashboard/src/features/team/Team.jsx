// Team (spec §14) — staff table, invite (gated by max_staff), role/location/
// active edit. Last-Owner protection enforced server-side (409); UI also guards.
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { UserPlus, Users } from 'lucide-react'
import api, { normalizeError } from '../../lib/api'
import { usePlan } from '../../hooks/usePlan'
import { useToast } from '../../hooks/useToast'
import Table from '../../components/Table'
import Badge from '../../components/Badge'
import Button from '../../components/Button'
import { Modal } from '../../components/Modal'
import { Input, Select } from '../../components/Field'
import { ROLES, SPECIALIZED_ROLES } from '../../lib/roles'

function useStaff() {
  return useQuery({
    queryKey: ['staff'],
    queryFn: async () => (await api.get('/staff')).data.results ?? [],
  })
}

export default function Team() {
  const { t } = useTranslation()
  const { atLimit, requireRoom, can } = usePlan()
  // Marketing/Designer roles need the specialized_roles plan capability (Growth+).
  const availableRoles = can('specialized_roles')
    ? ROLES
    : ROLES.filter((r) => !SPECIALIZED_ROLES.includes(r))
  const toast = useToast()
  const qc = useQueryClient()
  const { data: staff = [], isLoading } = useStaff()

  const [inviteOpen, setInviteOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('SCANNER')

  const ownerCount = staff.filter((s) => s.role === 'OWNER' && s.is_active).length

  const invite = useMutation({
    mutationFn: async () => (await api.post('/staff/invite', { email, role })).data,
    onSuccess: () => {
      toast.success(t('team.invited'))
      setInviteOpen(false)
      setEmail('')
      qc.invalidateQueries({ queryKey: ['staff'] })
    },
    onError: (err) => {
      const { code, message } = normalizeError(err)
      toast.error(code === 'PLAN_LIMIT' ? t('team.limit') : message)
    },
  })

  const patchStaff = useMutation({
    mutationFn: async ({ id, ...body }) => (await api.patch(`/staff/${id}`, body)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff'] }),
    onError: (err) => {
      const { code, message } = normalizeError(err)
      toast.error(code === 'CONFLICT' ? t('team.lastOwner') : message)
    },
  })

  function openInvite() {
    if (!requireRoom('max_staff')) return
    setInviteOpen(true)
  }

  const columns = [
    { key: 'name', label: t('team.name') },
    { key: 'email', label: t('team.email'), render: (r) => <span dir="ltr">{r.email}</span> },
    {
      key: 'role',
      label: t('team.role'),
      render: (r) => {
        const isLastOwner = r.role === 'OWNER' && ownerCount <= 1
        return (
          <Select
            name={`role-${r.id}`}
            value={r.role}
            onChange={(e) => patchStaff.mutate({ id: r.id, role: e.target.value })}
            options={availableRoles.map((x) => ({ value: x, label: t(`roles.${x}`) }))}
            disabled={isLastOwner}
          />
        )
      },
    },
    {
      key: 'is_active',
      label: t('team.status'),
      render: (r) => <Badge tone={r.is_active ? 'success' : 'neutral'}>{r.is_active ? t('team.active') : t('team.inactive')}</Badge>,
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-head text-2xl font-bold text-tx">{t('team.title')}</h1>
        <Button iconStart={UserPlus} onClick={openInvite} disabled={atLimit('max_staff')}>
          {t('team.invite')}
        </Button>
      </div>

      <Table
        columns={columns}
        rows={staff}
        loading={isLoading}
        emptyState={<div className="rounded-card border border-line bg-surface p-8 text-center text-tx-3"><Users size={28} className="mx-auto mb-2" />{t('team.empty')}</div>}
      />

      <Modal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        title={t('team.inviteTitle')}
        footer={
          <Button onClick={() => invite.mutate()} loading={invite.isPending} disabled={!email.trim()} className="w-full">
            {t('team.sendInvite')}
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          <Input name="email" type="email" label={t('team.email')} value={email} onChange={(e) => setEmail(e.target.value)} />
          <Select
            name="role"
            label={t('team.role')}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            options={availableRoles.map((x) => ({ value: x, label: t(`roles.${x}`) }))}
          />
        </div>
      </Modal>
    </div>
  )
}
