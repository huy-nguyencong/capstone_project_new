import { CircleNotchIcon } from '@phosphor-icons/react'
import { cx } from './cx'

export function Spinner({ size = 16, className }) {
  return <CircleNotchIcon size={size} className={cx('animate-spin', className)} />
}
