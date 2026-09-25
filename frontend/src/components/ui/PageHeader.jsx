export function PageHeader({ title, description, children }) {
  return (
    <header className="mb-5 flex flex-wrap items-end gap-4">
      <div className="min-w-[260px] flex-1">
        <h2 className="mb-1 text-2xl">{title}</h2>
        {description && <p className="text-muted m-0 text-[13px]">{description}</p>}
      </div>
      {children}
    </header>
  )
}
