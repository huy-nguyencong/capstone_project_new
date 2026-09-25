import { NavLink } from 'react-router'
import { cx } from '@/components/ui/cx'
import { NAVIGATION } from '@/constants/navigation'
import { Brand } from './Brand'
import { UserCard } from './UserCard'

export function Sidebar({ user, onLogout }) {
  const sections = NAVIGATION[user.role] ?? []
  return (
    <aside className="sticky top-0 flex h-screen flex-col gap-5 bg-[linear-gradient(180deg,var(--color-surface),color-mix(in_srgb,var(--color-surface)_55%,var(--color-bg)))] px-2.5 py-4 shadow-[1px_0_0_var(--color-divider)]">
      <Brand />
      <nav className="flex flex-col gap-4">
        {sections.map((sec) => (
          <div key={sec.section} className="flex flex-col gap-0.5">
            <div className="px-2.5 pb-1.5 text-[10px] tracking-[0.12em] text-neutral-500 uppercase">
              {sec.section}
            </div>
            {sec.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cx(
                    'relative flex items-center gap-2.5 rounded-[7px] px-2.5 py-2 text-[13px] no-underline',
                    isActive
                      ? 'bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200 hover:text-accent-200'
                      : 'text-neutral-300 hover:bg-[color-mix(in_srgb,var(--color-text)_6%,transparent)] hover:text-neutral-200',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cx(
                        'absolute top-2 bottom-2 -left-2.5 w-0.5 rounded-sm',
                        isActive ? 'bg-accent' : 'bg-transparent',
                      )}
                    />
                    <item.icon size={16} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
      <UserCard user={user} onLogout={onLogout} />
    </aside>
  )
}
