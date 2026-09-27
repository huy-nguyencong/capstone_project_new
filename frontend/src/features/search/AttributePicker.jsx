import { Chip } from '@/components/ui/Chip'
import { CLOTHING_TYPES, COLORS } from '@/constants/status'
import { attributesToPrompt } from '@/utils/search'

const colorOpts = (keys) =>
  keys.map((k) => ({ value: k, label: COLORS[k].label, swatch: COLORS[k].swatch }))

const GROUPS = [
  { key: 'shirt', label: 'Upper color', options: colorOpts(Object.keys(COLORS)) },
  { key: 'type', label: 'Upper type', options: CLOTHING_TYPES },
  {
    key: 'pants',
    label: 'Lower color',
    options: colorOpts(['black', 'blue', 'gray', 'beige', 'white']),
  },
  {
    key: 'bag',
    label: 'Backpack',
    options: [
      { value: true, label: 'Carrying a backpack' },
      { value: false, label: 'No backpack' },
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
