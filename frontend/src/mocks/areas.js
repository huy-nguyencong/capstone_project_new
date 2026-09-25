export const AREAS = ['Tòa A – Sảnh chính', 'Tòa B – Bãi đỗ xe', 'Khu C – Kho vận']

export const areaShort = (i) => AREAS[i].split(' – ')[0]

export const mockAreaIndex = (area) => Math.max(0, AREAS.indexOf(area?.name))
