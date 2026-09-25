export function PageHeader({ kicker, title, description, children }) {
  return (
    <header className="mb-5 flex flex-wrap items-end gap-4">
      <div className="min-w-[260px] flex-1">
        <div className="kicker text-accent-300">{kicker}</div>
        <h2 className="mt-1.5 mb-1 text-2xl">{title}</h2>
        {description && <p className="text-muted m-0 text-[13px]">{description}</p>}
      </div>
      {children}
    </header>
  )
}
