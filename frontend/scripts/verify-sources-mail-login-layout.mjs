import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const pagePath = resolve('pages/sources/index.vue')
const source = readFileSync(pagePath, 'utf8')

function assertContains(pattern, description) {
  if (!pattern.test(source)) {
    throw new Error(`Missing ${description}`)
  }
}

function assertNotContains(pattern, description) {
  if (pattern.test(source)) {
    throw new Error(`Unexpected ${description}`)
  }
}

assertContains(/w-full\s+max-w-lg[\s\S]*bg-background[\s\S]*shadow-xl/, 'solid bounded mailbox login dialog surface')
assertContains(/sm:grid-cols-\[minmax\(0,0\.35fr\)_minmax\(0,0\.65fr\)\]/, 'bounded provider/email grid tracks')
assertContains(/<div class="min-w-0 space-y-2">\s*<Label for="sources-mail-provider"/, 'provider column min-width reset')
assertContains(/<div class="min-w-0 space-y-2">\s*<Label for="sources-mail-address"/, 'email column min-width reset')
assertContains(/<select[\s\S]*id="sources-mail-provider"[\s\S]*class="h-9 w-full min-w-0/, 'provider select bounded width')
assertNotContains(/auth-shell-bg|auth-border|auth-shadow|auth-radius/, 'auth-only CSS variables in Sources mail dialog')

console.log('Sources mail login layout verification passed.')
