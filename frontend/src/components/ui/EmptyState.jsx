export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-col gap-2 px-2 py-12">
      {Icon && <Icon size={28} className="text-neutral-500" />}
      <div className="text-base">{title}</div>
      {children && <p className="text-muted m-0 max-w-[440px] text-[13px]">{children}</p>}
    </div>
  )
}
