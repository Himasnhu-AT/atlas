import Link from 'next/link'

import { store } from '@/lib/server/store'
import { AdminDeviceRevokeButton } from './device-revoke-button'

export default async function AdminDevicesPage() {
  const devices = await store().listAllDevices()
  const users = await store().listAllUsers()
  const usersMap = new Map(users.map((u) => [u.id, u.displayName]))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-display text-ink">Paired Devices</h1>
        <p className="mt-1 font-serif text-lead text-ink-soft">
          All desktop and local pairing tokens across learners.
        </p>
      </div>

      <div className="overflow-x-auto rounded-sheet border border-rule bg-paper">
        <table className="w-full border-collapse text-left text-caption">
          <thead>
            <tr className="border-b border-rule bg-paper-raised text-muted">
              <th className="px-4 py-3 font-medium">Device Name</th>
              <th className="px-4 py-3 font-medium">Platform</th>
              <th className="px-4 py-3 font-medium">App Version</th>
              <th className="px-4 py-3 font-medium">Learner</th>
              <th className="px-4 py-3 font-medium">Last Seen</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {devices.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted">
                  No paired devices found.
                </td>
              </tr>
            ) : (
              devices.map((device) => (
                <tr key={device.id} className="hover:bg-paper-raised">
                  <td className="px-4 py-3 font-medium text-ink">{device.name}</td>
                  <td className="px-4 py-3 text-muted capitalize">{device.platform}</td>
                  <td className="px-4 py-3 font-mono text-[12px] text-muted">
                    v{device.appVersion}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/users/${device.userId}`}
                      className="font-medium text-ink hover:underline"
                    >
                      {usersMap.get(device.userId) || device.userId.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-[12px] text-muted">
                    {new Date(device.lastSeenAt).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </td>
                  <td className="px-4 py-3">
                    {device.revokedAt ? (
                      <span className="inline-flex rounded bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
                        Revoked
                      </span>
                    ) : (
                      <span className="inline-flex rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                        Active
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <AdminDeviceRevokeButton
                      userId={device.userId}
                      deviceId={device.id}
                      isRevoked={Boolean(device.revokedAt)}
                    />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
