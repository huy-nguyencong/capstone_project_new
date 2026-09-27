import { cx } from '@/components/ui/cx'

export const APP_NAME = 'PRISM'
export const APP_TAGLINE = 'Person Retrieval via Image & Semantic Matching'

// Same mark as public/favicon.svg (without its tile): one beam enters the prism and splits
// into several rays — one person seen through many cameras and query modes.
export function PrismMark({ size = 20, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <path
        d="M2.5 19.2 10.4 17"
        stroke="var(--color-neutral-300)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M10.4 17 20.4 15"
        stroke="var(--color-accent)"
        strokeOpacity=".45"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M16 6.5 26.4 25H5.6Z"
        stroke="var(--color-accent)"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
      <path
        d="M20.4 15 29.5 10.8"
        stroke="var(--color-accent-300)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M20.4 15 29.5 15"
        stroke="var(--color-accent-400)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M20.4 15 29.5 19.2"
        stroke="var(--color-accent-600)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Brand({ size = 'md' }) {
  const lg = size === 'lg'
  return (
    <div className={cx('flex items-center', lg ? 'gap-2.5' : 'gap-[9px] px-2 py-0.5')}>
      <div
        className={cx(
          'grid place-items-center border border-accent bg-bg',
          lg
            ? 'size-[34px] rounded-md shadow-[0_0_18px_color-mix(in_srgb,var(--color-accent)_35%,transparent)]'
            : 'size-[28px] rounded-[7px]',
        )}
      >
        <PrismMark size={lg ? 24 : 20} />
      </div>
      <div className="flex min-w-0 flex-col leading-tight">
        <span
          className={cx('font-medium tracking-[0.08em]', lg ? 'text-[17px]' : 'text-[15px]')}
          title={APP_TAGLINE}
        >
          {APP_NAME}
        </span>
        {lg && <span className="text-[11px] text-neutral-400">{APP_TAGLINE}</span>}
      </div>
    </div>
  )
}
