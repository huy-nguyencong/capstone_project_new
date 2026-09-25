import { cx } from './cx'

const VARIANT = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  quiet: 'btn-quiet',
}

export function Button({
  variant = 'secondary',
  icon: Icon,
  iconRight: IconRight,
  type = 'button',
  className,
  children,
  ...props
}) {
  return (
    <button type={type} className={cx('btn', VARIANT[variant], className)} {...props}>
      {Icon && <Icon size={15} />}
      {children}
      {IconRight && <IconRight size={15} />}
    </button>
  )
}

export function IconButton({
  icon: Icon,
  label,
  variant = 'quiet',
  size = 16,
  className,
  ...props
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      className={cx('btn btn-icon', VARIANT[variant], className)}
      {...props}
    >
      <Icon size={size} />
    </button>
  )
}
