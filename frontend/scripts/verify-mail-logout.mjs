import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const pagePath = resolve('pages/mail/index.vue')
const source = readFileSync(pagePath, 'utf8')

function assertContains(pattern, description) {
  if (!pattern.test(source)) {
    throw new Error(`Missing ${description}`)
  }
}

assertContains(/const\s+isLoggingOut\s*=\s*ref\(false\)/, 'dedicated logout pending state')
assertContains(/async\s+function\s+logoutMailbox\s*\(\)/, 'logoutMailbox handler')
assertContains(/await\s+api\.logoutMailAccount\(session\)/, 'logout API call')
assertContains(/account\.value\s*=\s*\{[^}]*loggedIn:\s*false[^}]*\}/s, 'disconnected account assignment')
assertContains(/account\.value\s*=\s*\{[^}]*provider:\s*null[^}]*\}/s, 'disconnected account provider reset')
assertContains(/account\.value\s*=\s*\{[^}]*mailbox:\s*null[^}]*\}/s, 'disconnected account mailbox reset')
assertContains(/account\.value\s*=\s*\{[^}]*loggedInAt:\s*null[^}]*\}/s, 'disconnected account timestamp reset')
assertContains(/messages\.value\s*=\s*\[\]/, 'messages reset')
assertContains(/selectedMessage\.value\s*=\s*null/, 'selected message reset')
assertContains(/composeStatus\.value\s*=\s*''/, 'compose status reset')
assertContains(/mailboxStatus\.value\s*=\s*'Mailbox logged out\.'/, 'logout success status')
assertContains(/isComposeOpen\.value\s*=\s*false/, 'compose panel close')
assertContains(/accountError\.value\s*=\s*toApiMessage\(error,\s*'Unable to log out of the mailbox\.'\)/, 'account error failure path')
assertContains(/v-if="hasMailbox"[\s\S]*Log out mailbox/, 'connected-only logout button')
assertContains(/:disabled="isLoggingOut"/, 'logout-only disabled state')

console.log('Mail logout verification passed.')
