import { store } from '@/lib/server/store'
import { UserSearchTable } from './user-search'

export default async function AdminUsersPage() {
  const users = await store().listAllUsers()

  // Fetch XP for all users in parallel
  const usersWithXp = await Promise.all(
    users.map(async (u) => {
      const game = await store().gameFor(u.id)
      return {
        id: u.id,
        displayName: u.displayName,
        email: u.email,
        createdAt: u.createdAt,
        totalXp: game.totalXp,
      }
    }),
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-serif text-display text-ink">Learners Directory</h1>
        <p className="mt-1 font-serif text-lead text-ink-soft">
          Search, inspect individual student progress, and moderate standings.
        </p>
      </div>

      <UserSearchTable users={usersWithXp} />
    </div>
  )
}
