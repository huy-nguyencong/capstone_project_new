import {
  BackpackIcon,
  CoatHangerIcon,
  DressIcon,
  GenderFemaleIcon,
  GenderMaleIcon,
  HandbagIcon,
  HoodieIcon,
  PantsIcon,
  ShirtFoldedIcon,
  SuitcaseRollingIcon,
  TShirtIcon,
  ToteIcon,
} from '@phosphor-icons/react'
import { useId } from 'react'
import { Dropdown } from '@/components/ui/Dropdown'
import { ATTRIBUTE_GROUPS, COLOR_SWATCH, attributesToPrompt } from '@/constants/attributes'

const LOWER_KEYS = ['lower_type', 'lower_color']

const ICONS = {
  man: GenderMaleIcon,
  woman: GenderFemaleIcon,
  backpack: BackpackIcon,
  handbag: HandbagIcon,
  shoulder_bag: ToteIcon,
  suitcase: SuitcaseRollingIcon,
  t_shirt: TShirtIcon,
  shirt: ShirtFoldedIcon,
  sweater: HoodieIcon,
  jacket: CoatHangerIcon,
  coat: CoatHangerIcon,
  dress: DressIcon,
  pants: PantsIcon,
  jeans: PantsIcon,
  shorts: PantsIcon,
  skirt: DressIcon,
}

const withVisual = (options) =>
  options.map((o) => ({ ...o, icon: ICONS[o.value], swatch: COLOR_SWATCH[o.value] }))

function AttributeField({ group, value, disabled, onChange }) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{group.label}</label>
      <Dropdown
        id={id}
        value={value}
        disabled={disabled}
        placeholder="Bất kỳ"
        options={withVisual(group.options)}
        onChange={onChange}
      />
    </div>
  )
}

// Compact popup lists (same panel layout as the image/text search tabs). Group titles are
// Vietnamese UI labels; option values are English and are turned into an English sentence for
// the Text Encoder.
export function AttributePicker({ value, onChange }) {
  const dress = value.upper_type === 'dress'
  const set = (key, next) => {
    const updated = { ...value, [key]: next }
    // A dress covers the lower body, so lower clothing is cleared and locked.
    if (key === 'upper_type' && next === 'dress') LOWER_KEYS.forEach((k) => (updated[k] = null))
    onChange(updated)
  }
  const prompt = attributesToPrompt(value)

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-x-2.5 gap-y-3">
        {ATTRIBUTE_GROUPS.map((group) => (
          <AttributeField
            key={group.key}
            group={group}
            value={value[group.key]}
            disabled={dress && LOWER_KEYS.includes(group.key)}
            onChange={(next) => set(group.key, next)}
          />
        ))}
      </div>
      {dress && (
        <div className="text-[11px] text-neutral-400">Dress đã bao gồm trang phục phía dưới.</div>
      )}
      <div className="rounded-md bg-bg px-3 py-2.5 text-xs">
        <div className="mb-1 text-[10px] tracking-[0.1em] text-neutral-500 uppercase">
          Câu mô tả dùng để tìm kiếm
        </div>
        <div className={prompt ? 'text-neutral-200' : 'text-neutral-400'}>
          {prompt ?? 'Chưa chọn đặc điểm nào.'}
        </div>
      </div>
    </div>
  )
}
