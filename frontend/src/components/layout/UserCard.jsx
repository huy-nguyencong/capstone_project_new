import { MapPinIcon, SignOutIcon } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { ROLE_LABEL } from '@/constants/status'
import { initials } from '@/utils/format'

export function UserCard({ user, onLogout }) {
  const roleLabel = ROLE_LABEL[user.role] + (user.role === 'viewer' ? ' · Manager/Director' : '')
  return (
    <div className="mt-auto flex flex-col gap-2 rounded-md bg-[color-mix(in_srgb,var(--color-bg)_55%,transparent)] p-2.5 shadow-sm">
      <div className="flex items-center gap-2.5">
        <div className="grid size-[30px] flex-none place-items-center rounded-full bg-accent-900 text-xs font-medium text-accent-200">
          {initials(user.name)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px]">{user.name}</div>
          <div className="text-[11px] text-neutral-400">{roleLabel}</div>
        </div>
      </div>
      {user.role === 'operator' && user.area && (
        <div className="flex items-center gap-1.5 text-[11px] text-neutral-300">
          <MapPinIcon size={12} />
          {user.area.name}
        </div>
      )}
      <Button
        variant="secondary"
        icon={SignOutIcon}
        onClick={onLogout}
        className="justify-start text-xs"
      >
        Đăng xuất
      </Button>
    </div>
  )
}
