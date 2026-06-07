import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const assistantPage = resolve(scriptDir, '../pages/assistant/index.vue')
const source = readFileSync(assistantPage, 'utf8')

const requiredSnippets = [
  {
    label: 'Assistant shell is locked to the desktop viewport height',
    snippet: 'xl:h-[calc(100dvh-var(--header-height)-3rem)]',
  },
  {
    label: 'Assistant shell prevents document-level desktop overflow',
    snippet: 'xl:overflow-hidden',
  },
  {
    label: 'Assistant grid lets fixed-height columns shrink instead of expanding the page',
    snippet: 'grid h-full min-h-0 gap-4 overflow-hidden',
  },
  {
    label: 'Conversation column owns its internal scroll',
    snippet: 'flex min-h-0 flex-1 flex-col',
  },
  {
    label: 'Conversation list scrolls independently',
    snippet: 'mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1',
  },
  {
    label: 'Main message stream is the only vertical scroller in the chat column',
    snippet: 'min-h-0 flex-1 overflow-y-auto px-6 py-6',
  },
  {
    label: 'Composer stays pinned below the message stream',
    snippet: 'shrink-0 border-t border-border/80 px-6 py-5',
  },
]

const failures = requiredSnippets.filter(({ snippet }) => !source.includes(snippet))

if (failures.length > 0) {
  console.error('Assistant scroll layout regression checks failed:')
  for (const failure of failures) {
    console.error(`- ${failure.label}`)
  }
  process.exit(1)
}

console.log('Assistant scroll layout regression checks passed.')
