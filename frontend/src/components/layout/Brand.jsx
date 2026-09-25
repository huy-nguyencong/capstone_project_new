import { ScanIcon } from '@phosphor-icons/react'
import { cx } from '@/components/ui/cx'

export function Brand({ size = 'md' }) {
  const lg = size === 'lg'
  return (
    <div className={cx('flex items-center', lg ? 'gap-2.5' : 'gap-[9px] px-2 py-0.5')}>
      <div
        className={cx(
          'grid place-items-center border border-accent text-accent',
          lg
            ? 'size-[30px] rounded-md shadow-[0_0_18px_color-mix(in_srgb,var(--color-accent)_35%,transparent)]'
            : 'size-[26px] rounded-[7px]',
        )}
      >
        <ScanIcon size={lg ? 17 : 15} />
      </div>
      <span className={cx('font-medium', lg ? 'text-[17px]' : 'text-[15px]')}>VisionTrace</span>
    </div>
  )
}
