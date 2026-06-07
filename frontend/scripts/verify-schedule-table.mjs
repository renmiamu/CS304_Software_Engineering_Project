import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const storeFile = resolve(scriptDir, '../composables/useWorkspaceStore.ts')
const schedulePageFile = resolve(scriptDir, '../pages/schedule/index.vue')

const storeSource = readFileSync(storeFile, 'utf8')
const schedulePageSource = readFileSync(schedulePageFile, 'utf8')

const requiredSnippets = [
  {
    label: 'Blank custom schedule types are normalized to custom',
    source: storeSource,
    snippet: "schedule_type: normalizeCustomScheduleType(event.schedule_type)",
  },
  {
    label: 'Only explicit course events are excluded from custom schedule events',
    source: storeSource,
    snippet: "normalizeCustomScheduleType(event.schedule_type) !== 'course'",
  },
  {
    label: 'Sports event type label is English',
    source: schedulePageSource,
    snippet: "{ value: 'sports', label: 'Sports'",
  },
  {
    label: 'Weekday labels are English',
    source: schedulePageSource,
    snippet: "{ value: 7, label: 'Sunday' }",
  },
]

const forbiddenSnippets = [
  {
    label: 'Old schedule_type truthy filter must not remain',
    source: storeSource,
    snippet: 'response.filter(e => e.schedule_type && e.schedule_type !==',
  },
  {
    label: 'Schedule event type labels must not be Chinese',
    source: schedulePageSource,
    snippet: "label: '体育'",
  },
  {
    label: 'Schedule weekday labels must not be Chinese',
    source: schedulePageSource,
    snippet: "label: '周一'",
  },
  {
    label: 'Event data text must not be translated in the Schedule view',
    source: schedulePageSource,
    snippet: 'SCHEDULE_DISPLAY_TEXT_OVERRIDES',
  },
  {
    label: 'Event titles must render from backend data without display translation',
    source: schedulePageSource,
    snippet: 'displayScheduleText(',
  },
]

const missing = requiredSnippets.filter(({ source, snippet }) => !source.includes(snippet))
const forbidden = forbiddenSnippets.filter(({ source, snippet }) => source.includes(snippet))

if (missing.length > 0 || forbidden.length > 0) {
  console.error('Schedule table regression checks failed:')
  for (const failure of missing) {
    console.error(`- Missing: ${failure.label}`)
  }
  for (const failure of forbidden) {
    console.error(`- Forbidden: ${failure.label}`)
  }
  process.exit(1)
}

console.log('Schedule table regression checks passed.')
