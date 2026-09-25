import { Chip } from '@/components/ui/Chip'
import { CLOTHING_TYPES, COLORS } from '@/constants/status'
import { attributesToPrompt } from '@/utils/search'

const colorOpts = (keys) =>
  keys.map((k) => ({ value: k, label: COLORS[k].label, swatch: COLORS[k].swatch }))

const GROUPS = [
  { key: 'shirt', label: 'Màu áo', options: colorOpts(Object.keys(COLORS)) },
  {
    key: 'type',
    label: 'Loại trang phục',
    options: CLOTHING_TYPES.map((t) => ({ value: t, label: t })),
  },
  {
    key: 'pants',
    label: 'Màu quần',
    options: colorOpts(['black', 'blue', 'gray', 'beige', 'white']),
  },
  {
    key: 'bag',
    label: 'Ba lô',
    options: [
      { value: true, label: 'Có mang ba lô' },
      { value: false, label: 'Không mang' },
    ],
  },
]

export function AttributePicker({ value, onChange }) {
  const toggle = (key, v) => onChange({ ...value, [key]: value[key] === v ? null : v })

  return (
    <div className="flex flex-col gap-3">
      {GROUPS.map((g) => (
        <div key={g.key}>
          <div className="mb-1.5 text-xs text-neutral-300">{g.label}</div>
          <div className="flex flex-wrap gap-1.5">
            {g.options.map((o) => (
              <Chip
                key={String(o.value)}
                active={value[g.key] === o.value}
                swatch={o.swatch}
                onClick={() => toggle(g.key, o.value)}
              >
                {o.label}
              </Chip>
            ))}
          </div>
        </div>
      ))}
      <div className="rounded-md bg-bg px-3 py-2.5 text-xs">
        <div className="mb-1 text-[10px] tracking-[0.1em] text-neutral-500 uppercase">
          Câu mô tả gửi tới Text Encoder
        </div>
        <div className="text-neutral-200">{attributesToPrompt(value)}</div>
      </div>
    </div>
  )
}
