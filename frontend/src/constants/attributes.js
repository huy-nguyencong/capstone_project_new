// Attribute search vocabulary — mirrors backend services/searches.py (ATTRIBUTE_*). Group titles
// are Vietnamese UI labels; option values/labels stay English because they are composed into the
// English query sentence.
export const COLOR_SWATCH = {
  black: 'oklch(0.3 0.01 260)',
  white: 'oklch(0.93 0.01 260)',
  gray: 'oklch(0.62 0.01 260)',
  red: 'oklch(0.58 0.16 25)',
  blue: 'oklch(0.55 0.12 250)',
  navy: 'oklch(0.36 0.09 265)',
  green: 'oklch(0.58 0.1 150)',
  yellow: 'oklch(0.82 0.13 90)',
  brown: 'oklch(0.45 0.06 55)',
  beige: 'oklch(0.78 0.04 70)',
}

const colors = (values) =>
  values.map((value) => ({ value, label: value[0].toUpperCase() + value.slice(1) }))

export const ATTRIBUTE_GROUPS = [
  {
    key: 'gender',
    label: 'Giới tính',
    options: [
      { value: 'man', label: 'Man' },
      { value: 'woman', label: 'Woman' },
    ],
  },
  {
    key: 'carrying',
    label: 'Vật mang theo',
    options: [
      { value: 'backpack', label: 'Backpack' },
      { value: 'handbag', label: 'Handbag' },
    ],
  },
  {
    key: 'upper_type',
    label: 'Loại áo',
    options: [
      { value: 't_shirt', label: 'T-shirt', word: 't-shirt' },
      { value: 'shirt', label: 'Shirt', word: 'shirt' },
      { value: 'sweater', label: 'Sweater', word: 'sweater' },
      { value: 'jacket', label: 'Jacket', word: 'jacket' },
      { value: 'coat', label: 'Coat', word: 'coat' },
      { value: 'dress', label: 'Dress', word: 'dress' },
    ],
  },
  {
    key: 'upper_color',
    label: 'Màu áo',
    options: colors([
      'black',
      'white',
      'gray',
      'red',
      'blue',
      'navy',
      'green',
      'yellow',
      'brown',
      'beige',
    ]),
  },
  {
    key: 'lower_type',
    label: 'Loại quần/váy',
    options: [
      { value: 'pants', label: 'Pants', word: 'pants' },
      { value: 'jeans', label: 'Jeans', word: 'jeans' },
      { value: 'shorts', label: 'Shorts', word: 'shorts' },
      { value: 'skirt', label: 'Skirt', word: 'skirt' },
    ],
  },
  {
    key: 'lower_color',
    label: 'Màu quần/váy',
    options: colors(['black', 'white', 'gray', 'blue', 'brown', 'beige']),
  },
]

export const EMPTY_ATTRIBUTES = Object.fromEntries(ATTRIBUTE_GROUPS.map((g) => [g.key, null]))

const word = (key, value) =>
  ATTRIBUTE_GROUPS.find((g) => g.key === key).options.find((o) => o.value === value)?.word

// Mirrors backend attributes_prompt so the preview is exactly the sentence that is encoded.
export const attributesToPrompt = (a) => {
  const garments = []
  if (a.upper_type || a.upper_color) {
    const words = [a.upper_color, a.upper_type ? word('upper_type', a.upper_type) : 'top']
    garments.push(`a ${words.filter(Boolean).join(' ')}`)
  }
  if (a.lower_type || a.lower_color) {
    const noun = a.lower_type ? word('lower_type', a.lower_type) : 'pants'
    const phrase = [a.lower_color, noun].filter(Boolean).join(' ')
    garments.push(noun === 'skirt' ? `a ${phrase}` : phrase)
  }
  const parts = garments.length ? [`wearing ${garments.join(' and ')}`] : []
  if (a.carrying) parts.push(`carrying a ${a.carrying}`)
  const subject = a.gender ? `A ${a.gender}` : 'A person'
  if (!parts.length && !a.gender) return null
  return parts.length ? `${subject} ${parts.join(', ')}.` : `${subject}.`
}
