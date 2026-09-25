import { cx } from './cx'

export function Tag({ variant = 'neutral', className, children }) {
  return <span className={cx('tag', `tag-${variant}`, className)}>{children}</span>
}
