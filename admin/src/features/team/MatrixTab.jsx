import { Loader2, Check } from 'lucide-react'
import { useRbacMatrix } from './api'
import Badge from '../../components/Badge'

export default function MatrixTab() {
  const { data, isLoading } = useRbacMatrix()
  if (isLoading || !data) return <Loader2 className="mx-auto mt-10 animate-spin text-tx-3" />

  const { permissions, roles } = data

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-tx-3">
        The single source of truth for what each role may do. Reads (viewing lists
        and details) are open to any admin; the matrix gates mutations and tools.
      </p>
      <div className="overflow-x-auto rounded-card border border-line bg-surface">
        <table className="w-full text-sm">
          <thead className="border-b border-line text-tx-3">
            <tr className="text-left">
              <th className="px-4 py-3 font-medium">Permission</th>
              {roles.map((r) => (
                <th key={r.role} className="px-3 py-3 text-center font-medium">
                  <div>{r.label}</div>
                  {r.mfa_required && (
                    <div className="mt-1">
                      <Badge tone="warn">MFA</Badge>
                    </div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {permissions.map((perm) => (
              <tr key={perm} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2.5 font-num text-tx-2">{perm}</td>
                {roles.map((r) => (
                  <td key={r.role} className="px-3 py-2.5 text-center">
                    {r.permissions.includes(perm) ? (
                      <Check size={16} className="mx-auto text-success" />
                    ) : (
                      <span className="text-tx-3">·</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
