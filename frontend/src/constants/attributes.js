// Attribute search vocabulary — mirrors backend services/searches.py (ATTRIBUTE_*). Group titles
// are Vietnamese UI labels; option values/labels stay English because they are composed into the
// English query sentence.
export const COLOR_SWATCH = {
  black: 'oklch(0.3 0.01 260)',
  white: 'oklch(0.93 0.01 260)',
  gray: 'oklch(0.62 0.01 260)',
  red: 'oklch(0.58 0.16 25)',
  pink: 'oklch(0.78 0.1 0)',
  purple: 'oklch(0.5 0.14 305)',
  orange: 'oklch(0.72 0.15 55)',
  blue: 'oklch(0.55 0.12 250)',
  navy: 'oklch(0.36 0.09 265)',
  green: 'oklch(0.58 0.1 150)',
  yellow: 'oklch(0.82 0.13 90)',
  brown: 'oklch(0.45 0.06 55)',
  beige: 'oklch(0.78 0.04 70)',
  khaki: 'oklch(0.7 0.06 95)',
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
      { value: 'backpack', label: 'Backpack', phrase: 'carrying a backpack' },
      { value: 'handbag', label: 'Handbag', phrase: 'carrying a handbag' },
      { value: 'shoulder_bag', label: 'Shoulder bag', phrase: 'carrying a shoulder bag' },
      // A suitcase is pulled, not carried (same phrase as the backend).
      { value: 'suitcase', label: 'Suitcase', phrase: 'pulling a suitcase' },
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
      'pink',
      'purple',
      'orange',
      'yellow',
      'green',
      'blue',
      'navy',
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
    options: colors(['black', 'white', 'gray', 'blue', 'navy', 'green', 'brown', 'beige', 'khaki']),
  },
]

export const EMPTY_ATTRIBUTES = Object.fromEntries(ATTRIBUTE_GROUPS.map((g) => [g.key, null]))

const option = (key, value) =>
  ATTRIBUTE_GROUPS.find((g) => g.key === key).options.find((o) => o.value === value)
const word = (key, value) => option(key, value)?.word
const withArticle = (phrase) => `${/^[aeiou]/.test(phrase) ? 'an' : 'a'} ${phrase}`

// Mirrors backend attributes_prompt so the preview is exactly the sentence that is encoded.
export const attributesToPrompt = (a) => {
  const garments = []
  if (a.upper_type || a.upper_color) {
    const words = [a.upper_color, a.upper_type ? word('upper_type', a.upper_type) : 'top']
    garments.push(withArticle(words.filter(Boolean).join(' ')))
  }
  if (a.lower_type || a.lower_color) {
    const noun = a.lower_type ? word('lower_type', a.lower_type) : 'pants'
    const phrase = [a.lower_color, noun].filter(Boolean).join(' ')
    garments.push(noun === 'skirt' ? withArticle(phrase) : phrase)
  }
  const parts = garments.length ? [`wearing ${garments.join(' and ')}`] : []
  if (a.carrying) parts.push(option('carrying', a.carrying).phrase)
  const subject = a.gender ? `A ${a.gender}` : 'A person'
  if (!parts.length && !a.gender) return null
  return parts.length ? `${subject} ${parts.join(', ')}.` : `${subject}.`
}
