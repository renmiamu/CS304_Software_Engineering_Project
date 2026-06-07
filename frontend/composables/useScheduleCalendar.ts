import type { TisScheduleCourse, ScheduleEvent } from '~/types/tis'

export type CalendarViewMode = 'week' | 'month'

export interface ScheduleRenderableItem {
  id: string
  title: string
  type: string
  weekday: number
  startSlot: number
  endSlot: number
  date: string
  startTime: string
  endTime: string
  location: string
  teacher: string
  zIndex: number
  raw: TisScheduleCourse
}

interface BaseScheduleItem {
  id: string
  title: string
  type: string
  weekday: number
  startSlot: number
  endSlot: number
  startTime: string
  endTime: string
  location: string
  teacher: string
  weeks: Set<number> | null
  raw: TisScheduleCourse
}

export const SEMESTER_START_DATE = '2026-02-23'

export const SLOT_DEFINITIONS = [
  { slot: 1, start: '08:00', end: '08:50' },
  { slot: 2, start: '09:00', end: '09:50' },
  { slot: 3, start: '10:20', end: '11:10' },
  { slot: 4, start: '11:20', end: '12:10' },
  { slot: 5, start: '14:00', end: '14:50' },
  { slot: 6, start: '15:00', end: '15:50' },
  { slot: 7, start: '16:20', end: '17:10' },
  { slot: 8, start: '17:20', end: '18:10' },
  { slot: 9, start: '19:00', end: '19:50' },
  { slot: 10, start: '20:00', end: '20:50' },
  { slot: 11, start: '21:00', end: '21:50' },
  { slot: 12, start: '21:50', end: '22:40' },
] as const

const SLOT_INDEX = new Map<number, { start: string, end: string, startMinutes: number, endMinutes: number }>()
for (const slot of SLOT_DEFINITIONS) {
  SLOT_INDEX.set(slot.slot, {
    start: slot.start,
    end: slot.end,
    startMinutes: toMinutes(slot.start),
    endMinutes: toMinutes(slot.end),
  })
}

const WEEKDAY_MAP: Record<string, number> = {
  '星期一': 1,
  '星期二': 2,
  '星期三': 3,
  '星期四': 4,
  '星期五': 5,
  '星期六': 6,
  '星期日': 7,
  '周一': 1,
  '周二': 2,
  '周三': 3,
  '周四': 4,
  '周五': 5,
  '周六': 6,
  '周日': 7,
  monday: 1,
  tuesday: 2,
  wednesday: 3,
  thursday: 4,
  friday: 5,
  saturday: 6,
  sunday: 7,
  mon: 1,
  tue: 2,
  wed: 3,
  thu: 4,
  fri: 5,
  sat: 6,
  sun: 7,
  '1': 1,
  '2': 2,
  '3': 3,
  '4': 4,
  '5': 5,
  '6': 6,
  '7': 7,
}

const WEEKDAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function formatDateKey(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function parseQueryDate(value: unknown) {
  if (typeof value !== 'string') {
    return null
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null
  }

  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return startOfDay(date)
}

export function parseViewMode(value: unknown): CalendarViewMode {
  return value === 'month' ? 'month' : 'week'
}

export function cloneDate(date: Date) {
  return new Date(date.getTime())
}

export function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

export function addDays(date: Date, days: number) {
  const next = startOfDay(date)
  next.setDate(next.getDate() + days)
  return next
}

export function addMonths(date: Date, months: number) {
  const next = startOfDay(date)
  next.setMonth(next.getMonth() + months)
  return next
}

export function getWeekStart(date: Date) {
  const day = date.getDay() === 0 ? 7 : date.getDay()
  return addDays(startOfDay(date), 1 - day)
}

export function getWeekEnd(date: Date) {
  return addDays(getWeekStart(date), 6)
}

export function getMonthStart(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function getMonthEnd(date: Date) {
  return new Date(date.getFullYear(), date.getMonth() + 1, 0)
}

export function getMonthGridRange(date: Date) {
  const monthStart = getMonthStart(date)
  const monthEnd = getMonthEnd(date)
  const startOffset = (monthStart.getDay() + 6) % 7
  const endOffset = 6 - ((monthEnd.getDay() + 6) % 7)

  return {
    start: addDays(monthStart, -startOffset),
    end: addDays(monthEnd, endOffset),
    monthStart,
    monthEnd,
  }
}

export function createDateRange(start: Date, end: Date) {
  const dates: Date[] = []
  let cursor = startOfDay(start)
  const target = startOfDay(end)

  while (cursor.getTime() <= target.getTime()) {
    dates.push(cursor)
    cursor = addDays(cursor, 1)
  }

  return dates
}

export function getWeekdayLabel(index: number) {
  return WEEKDAY_LABELS[index] ?? 'Unknown'
}

export function formatWeekRangeLabel(anchorDate: Date) {
  const start = getWeekStart(anchorDate)
  const end = getWeekEnd(anchorDate)
  const sameYear = start.getFullYear() === end.getFullYear()

  if (sameYear) {
    return `${formatDateLabel(start, { month: 'short', day: 'numeric' })} - ${formatDateLabel(end, { month: 'short', day: 'numeric', year: 'numeric' })}`
  }

  return `${formatDateLabel(start, { month: 'short', day: 'numeric', year: 'numeric' })} - ${formatDateLabel(end, { month: 'short', day: 'numeric', year: 'numeric' })}`
}

export function formatMonthLabel(anchorDate: Date) {
  return formatDateLabel(anchorDate, { month: 'long', year: 'numeric' })
}

export function toScheduleRenderableItems(courses: TisScheduleCourse[], fromDate: Date, toDate: Date) {
  const baseItems = courses
    .map((course, index) => normalizeCourse(course, index))
    .filter((item): item is BaseScheduleItem => item !== null)

  if (baseItems.length === 0) {
    return []
  }

  const days = createDateRange(fromDate, toDate)
  const items: ScheduleRenderableItem[] = []

  for (const day of days) {
    const weekday = day.getDay() === 0 ? 7 : day.getDay()
    const weekNumber = getSemesterWeekNumber(day)

    for (const item of baseItems) {
      if (item.weekday !== weekday) {
        continue
      }

      if (item.weeks && (weekNumber === null || !item.weeks.has(weekNumber))) {
        continue
      }

      items.push({
        id: `${item.id}-${formatDateKey(day)}`,
        title: item.title,
        type: item.type,
        weekday,
        startSlot: item.startSlot,
        endSlot: item.endSlot,
        date: formatDateKey(day),
        startTime: item.startTime,
        endTime: item.endTime,
        location: item.location,
        teacher: item.teacher,
        zIndex: 0,
        raw: item.raw,
      })
    }
  }

  return items
}

export function toCustomScheduleRenderableItems(events: ScheduleEvent[], fromDate: Date, toDate: Date) {
  const items: ScheduleRenderableItem[] = []

  for (const event of events) {
    if (event.weekday == null || event.weekday < 1 || event.weekday > 7) continue

    const startMinutes = parseTimeValue(event.start_time)
    const endMinutes = parseTimeValue(event.end_time)
    if (startMinutes === null || endMinutes === null) continue

    const slots = parseSlotsFromTimeRange(event.start_time, event.end_time)
    const startSlot = slots?.startSlot ?? Math.max(0, Math.floor(startMinutes / 60) + 1)
    const endSlot = slots?.endSlot ?? Math.max(startSlot, Math.floor(endMinutes / 60) + 1)

    const days = createDateRange(fromDate, toDate)
    for (const day of days) {
      const weekday = day.getDay() === 0 ? 7 : day.getDay()
      if (weekday !== event.weekday) continue

      const type = event.schedule_type || 'custom'
      items.push({
        id: `custom-${event.schedule_id}-${formatDateKey(day)}`,
        title: event.name,
        type,
        weekday,
        startSlot,
        endSlot,
        date: formatDateKey(day),
        startTime: normalizeTimeString(event.start_time) ?? event.start_time,
        endTime: normalizeTimeString(event.end_time) ?? event.end_time,
        location: event.location,
        teacher: event.teacher,
        zIndex: event.schedule_id,
        raw: {
          course_name: event.name,
          teacher: event.teacher,
          weekday: String(event.weekday),
          location: event.location,
          schedule_type: event.schedule_type,
          start_time: event.start_time,
          end_time: event.end_time,
          description: event.description,
        } as TisScheduleCourse,
      })
    }
  }

  return items
}

function normalizeCourse(course: TisScheduleCourse, index: number): BaseScheduleItem | null {
  const weekday = parseWeekday(course.weekday)
  if (!weekday) {
    return null
  }

  const slots = resolveSlots(course)
  if (!slots) {
    return null
  }

  const weeksText = resolveWeeksText(course)
  const weeks = parseWeeks(weeksText)
  const startSlot = SLOT_INDEX.get(slots.startSlot)
  const endSlot = SLOT_INDEX.get(slots.endSlot)
  if (!startSlot || !endSlot) {
    return null
  }

  const type = typeof course.schedule_type === 'string' && course.schedule_type.trim()
    ? course.schedule_type.trim()
    : 'course'

  const title = typeof course.course_name === 'string' && course.course_name.trim()
    ? course.course_name.trim()
    : 'Untitled schedule'

  const startTime = normalizeTimeString(course.start_time) ?? startSlot.start
  const endTime = normalizeTimeString(course.end_time) ?? endSlot.end

  return {
    id: `${index}-${title}-${weekday}-${slots.startSlot}-${slots.endSlot}`,
    title,
    type,
    weekday,
    startSlot: slots.startSlot,
    endSlot: slots.endSlot,
    startTime,
    endTime,
    location: typeof course.location === 'string' ? course.location.trim() : '',
    teacher: typeof course.teacher === 'string' ? course.teacher.trim() : '',
    weeks,
    raw: course,
  }
}

function resolveSlots(course: TisScheduleCourse) {
  const fromTime = parseSlotsFromTimeRange(course.start_time, course.end_time)
  if (fromTime) {
    return fromTime
  }

  const textCandidates = [
    typeof course.time_slots === 'string' ? course.time_slots : '',
    typeof course.description === 'string' ? course.description : '',
  ]

  for (const text of textCandidates) {
    const parsed = parseSlotsFromText(text)
    if (parsed) {
      return parsed
    }
  }

  return null
}

function resolveWeeksText(course: TisScheduleCourse) {
  if (typeof course.weeks === 'string' && course.weeks.trim()) {
    return course.weeks.trim()
  }

  if (typeof course.description !== 'string' || !course.description.trim()) {
    return ''
  }

  const parts = course.description.split('|').map(part => part.trim()).filter(Boolean)
  return parts.find(part => part.includes('周')) ?? ''
}

function parseWeekday(value?: string) {
  if (!value) {
    return null
  }
  const normalized = value.trim()
  const lower = normalized.toLowerCase()
  return WEEKDAY_MAP[normalized] ?? WEEKDAY_MAP[lower] ?? null
}

function parseSlotsFromText(value: string) {
  if (!value) {
    return null
  }

  const normalized = value.replace(/[，；。]/g, ' ')
  const direct = normalized.match(/(?:^|\s)第?\s*(\d{1,2})\s*(?:[-~到至—–,，、]\s*第?\s*(\d{1,2}))?\s*节(?:\s|$)/)
  if (direct) {
    const startSlot = Number.parseInt(direct[1], 10)
    const endSlot = Number.parseInt(direct[2] || direct[1], 10)
    return normalizeSlotRange(startSlot, endSlot)
  }

  const range = normalized.match(/(?:^|\s)(\d{1,2})\s*[-~到至—–,，、]\s*(\d{1,2})(?:\s|$)/)
  if (range) {
    const startSlot = Number.parseInt(range[1], 10)
    const endSlot = Number.parseInt(range[2], 10)
    return normalizeSlotRange(startSlot, endSlot)
  }

  const single = normalized.match(/(?:^|\s)(\d{1,2})\s*节(?:\s|$)/)
  if (single) {
    const slot = Number.parseInt(single[1], 10)
    return normalizeSlotRange(slot, slot)
  }

  return null
}

function parseSlotsFromTimeRange(startTime?: string, endTime?: string) {
  const startMinutes = parseTimeValue(startTime)
  const endMinutes = parseTimeValue(endTime)

  if (startMinutes === null || endMinutes === null || endMinutes <= startMinutes) {
    return null
  }

  const overlapped: number[] = []
  for (const definition of SLOT_DEFINITIONS) {
    const item = SLOT_INDEX.get(definition.slot)
    if (!item) {
      continue
    }

    const isOverlapped = item.startMinutes < endMinutes && item.endMinutes > startMinutes
    if (isOverlapped) {
      overlapped.push(definition.slot)
    }
  }

  if (overlapped.length === 0) {
    return null
  }

  const startSlot = Math.min(...overlapped)
  const endSlot = Math.max(...overlapped)
  return normalizeSlotRange(startSlot, endSlot)
}

function normalizeSlotRange(startSlot: number, endSlot: number) {
  if (!Number.isFinite(startSlot) || !Number.isFinite(endSlot)) {
    return null
  }

  const minSlot = Math.min(startSlot, endSlot)
  const maxSlot = Math.max(startSlot, endSlot)

  if (minSlot < 1 || maxSlot > 10) {
    return null
  }

  return {
    startSlot: minSlot,
    endSlot: maxSlot,
  }
}

function parseWeeks(value: string) {
  if (!value) {
    return null
  }

  const weeks = new Set<number>()
  for (const match of value.matchAll(/(\d{1,2})\s*[-~到至—–,，、]\s*(\d{1,2})/g)) {
    const start = Number.parseInt(match[1], 10)
    const end = Number.parseInt(match[2], 10)
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      continue
    }
    const from = Math.min(start, end)
    const to = Math.max(start, end)
    for (let week = from; week <= to; week += 1) {
      weeks.add(week)
    }
  }

  const stripped = value.replace(/\d{1,2}\s*[-~到至—–,，、]\s*\d{1,2}/g, ' ')
  for (const match of stripped.matchAll(/(\d{1,2})/g)) {
    const week = Number.parseInt(match[1], 10)
    if (Number.isFinite(week)) {
      weeks.add(week)
    }
  }

  if (weeks.size === 0) {
    return null
  }

  const onlyOdd = /单/.test(value) && !/双/.test(value)
  const onlyEven = /双/.test(value) && !/单/.test(value)

  if (!onlyOdd && !onlyEven) {
    return weeks
  }

  const filtered = new Set<number>()
  for (const week of weeks) {
    if (onlyOdd && week % 2 === 1) {
      filtered.add(week)
    }
    if (onlyEven && week % 2 === 0) {
      filtered.add(week)
    }
  }

  return filtered.size > 0 ? filtered : weeks
}

function getSemesterWeekNumber(date: Date) {
  const semesterStart = parseQueryDate(SEMESTER_START_DATE)
  if (!semesterStart) {
    return null
  }

  const current = startOfDay(date)
  const diffMs = current.getTime() - semesterStart.getTime()
  if (diffMs < 0) {
    return null
  }

  const diffDays = Math.floor(diffMs / (24 * 60 * 60 * 1000))
  return Math.floor(diffDays / 7) + 1
}

function parseTimeValue(value?: string) {
  if (typeof value !== 'string' || !value.trim()) {
    return null
  }

  const match = value.match(/(\d{1,2}):(\d{2})/)
  if (!match) {
    return null
  }

  const hour = Number.parseInt(match[1], 10)
  const minute = Number.parseInt(match[2], 10)
  if (!Number.isFinite(hour) || !Number.isFinite(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    return null
  }

  return hour * 60 + minute
}

function normalizeTimeString(value?: string) {
  const total = parseTimeValue(value)
  if (total === null) {
    return null
  }

  const hour = String(Math.floor(total / 60)).padStart(2, '0')
  const minute = String(total % 60).padStart(2, '0')
  return `${hour}:${minute}`
}

function formatDateLabel(date: Date, options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('en-US', options).format(date)
}

function toMinutes(value: string) {
  const [hour, minute] = value.split(':').map(item => Number.parseInt(item, 10))
  return hour * 60 + minute
}
