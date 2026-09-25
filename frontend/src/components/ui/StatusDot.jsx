import { TONE } from '@/constants/status'
import { cx } from './cx'

export function Dot({ tone = 'mute', color, size = 7, className }) {
  return (
    <span
      className={cx('inline-block flex-none rounded-full', className)}
      style={{ width: size, height: size, background: color ?? TONE[tone] }}
    />
  )
}

export function StatusDot({ tone, label, className }) {
  return (
    <span
      className={cx('inline-flex items-center gap-[7px] text-[13px] whitespace-nowrap', className)}
    >
      <Dot tone={tone} />
      {label}
    </span>
  )
}
