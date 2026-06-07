export const THEME_COLORS = [
  { name: 'default', value: '#EC6C00' },
  { name: 'blue', value: 'oklch(0.623 0.214 259.815)' },
  { name: 'green', value: 'oklch(0.723 0.219 149.579)' },
  { name: 'red', value: 'oklch(0.637 0.237 25.331)' },
  { name: 'rose', value: 'oklch(0.645 0.246 16.439)' },
  { name: 'violet', value: 'oklch(0.606 0.25 292.717)' },
  { name: 'orange', value: '#EC6C00' },
  { name: 'yellow', value: 'oklch(0.795 0.184 86.047)' },
  { name: 'teal', value: 'oklch(0.6 0.118 184.704)' },
] as const

export const THEME_TYPES = ['default', 'scaled', 'mono'] as const

export type ThemeColor = (typeof THEME_COLORS)[number]['name']
export type ThemeType = (typeof THEME_TYPES)[number]
