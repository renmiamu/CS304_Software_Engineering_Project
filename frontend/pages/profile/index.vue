<script setup lang="ts">
import {
  IconBuildingCommunity,
  IconCalendar,
  IconChartBar,
  IconHome,
  IconId,
  IconMail,
  IconPhone,
  IconSchool,
  IconTrophy,
  IconUserCircle,
} from '@tabler/icons-vue'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import type { Component } from 'vue'
import type { IdentityCardData } from '~/types/app'

definePageMeta({
  layout: 'app',
})

const workspace = useWorkspaceStore()

const identityCard = computed(() => workspace.identityCard.value)
const interestDraft = ref('')
const interestSaving = ref(false)
const interestStatus = ref('')
const interestError = ref('')

watch(
  () => identityCard.value.interest,
  (value) => {
    if (!interestSaving.value) {
      interestDraft.value = value
    }
  },
  { immediate: true },
)

async function saveInterests() {
  interestSaving.value = true
  interestError.value = ''
  interestStatus.value = ''
  try {
    await workspace.saveIdentityInterest(interestDraft.value)
    interestStatus.value = 'Interests saved.'
  }
  catch (error) {
    const message = error && typeof error === 'object' && 'message' in error
      ? String((error as { message: unknown }).message)
      : 'Unable to save interests.'
    interestError.value = message
  }
  finally {
    interestSaving.value = false
  }
}

const identityPhotoSrc = computed(() => {
  const photo = identityCard.value.photo.trim()
  if (photo.startsWith('data:image/') || photo.startsWith('http://') || photo.startsWith('https://')) {
    return photo
  }
  return ''
})

const identityInitials = computed(() => {
  const fromName = identityCard.value.name.trim()
  if (fromName) {
    return fromName.slice(0, 1).toUpperCase()
  }

  const fromId = identityCard.value.user_id.trim()
  if (fromId) {
    return fromId.slice(-2).toUpperCase()
  }

  return 'ID'
})

type IdentityDisplayKey = Exclude<keyof IdentityCardData, 'photo' | 'interest' | 'pinyin_name'>

const metricFields: Array<{
  key: IdentityDisplayKey
  label: string
  icon: Component
}> = [
  { key: 'gpa', label: 'GPA', icon: IconChartBar },
  { key: 'rank', label: 'Rank', icon: IconTrophy },
  { key: 'user_id', label: 'Student ID', icon: IconId },
]

const campusFields: Array<{
  key: IdentityDisplayKey
  label: string
  icon: Component
  wide?: boolean
}> = [
  { key: 'college', label: 'College', icon: IconSchool },
  { key: 'department', label: 'Department', icon: IconBuildingCommunity },
  { key: 'dormitory', label: 'Dormitory', icon: IconHome, wide: true },
]

const personalFields: Array<{
  key: IdentityDisplayKey
  label: string
  icon: Component
  wide?: boolean
}> = [
  { key: 'gender', label: 'Gender', icon: IconUserCircle },
  { key: 'birth_date', label: 'Birth Date', icon: IconCalendar },
  { key: 'phone', label: 'Phone', icon: IconPhone },
  { key: 'email', label: 'Email', icon: IconMail, wide: true },
]

function displayValue(value: string) {
  const trimmed = value.trim()
  return trimmed || '-'
}
</script>

<template>
  <div class="w-full flex flex-col gap-4">
    <main class="@container/main flex flex-1 flex-col">
      <div class="*:data-[slot=card]:bg-gradient-to-t *:data-[slot=card]:shadow-xs">
        <Card class="overflow-hidden py-0">
          <div class="grid lg:grid-cols-[minmax(13rem,16rem)_minmax(0,1fr)]">
            <aside
              class="flex flex-col items-center gap-4 border-b bg-muted/40 px-5 py-6 text-center lg:border-r lg:border-b-0 lg:py-8"
            >
              <Avatar class="h-44 w-32 shrink-0 rounded-xl bg-muted shadow-sm sm:h-48 sm:w-36">
                <AvatarImage
                  v-if="identityPhotoSrc"
                  :src="identityPhotoSrc"
                  alt="Identity photo"
                  class="h-full w-full rounded-xl object-cover object-top"
                />
                <AvatarFallback class="rounded-xl text-2xl font-semibold">
                  {{ identityInitials }}
                </AvatarFallback>
              </Avatar>

              <div class="min-w-0 w-full space-y-1">
                <p class="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  Student
                </p>
                <h2 class="break-words text-2xl font-semibold leading-tight sm:text-[1.65rem]">
                  {{ displayValue(identityCard.name) }}
                </h2>
                <p class="break-all font-mono text-sm text-muted-foreground">
                  {{ displayValue(identityCard.user_id) }}
                </p>
              </div>

              <div
                v-if="identityCard.college.trim() || identityCard.department.trim()"
                class="mt-auto w-full space-y-1 border-t pt-4 text-xs leading-5 text-muted-foreground"
              >
                <p v-if="identityCard.college.trim()" class="break-words">
                  {{ displayValue(identityCard.college) }}
                </p>
                <p v-if="identityCard.department.trim()" class="break-words">
                  {{ displayValue(identityCard.department) }}
                </p>
              </div>
            </aside>

            <CardContent class="flex flex-col gap-6 p-5 sm:p-6 lg:gap-7 lg:p-7">
              <section aria-label="Key metrics">
                <div class="grid gap-3 sm:grid-cols-3">
                  <div
                    v-for="field in metricFields"
                    :key="field.key"
                    class="rounded-lg border bg-muted/40 px-4 py-3"
                  >
                    <div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                      <component :is="field.icon" class="size-4 shrink-0" />
                      <span>{{ field.label }}</span>
                    </div>
                    <p class="mt-2 break-words text-xl font-semibold leading-tight sm:text-2xl">
                      {{ displayValue(identityCard[field.key]) }}
                    </p>
                  </div>
                </div>
              </section>

              <section class="space-y-3">
                <CardHeader class="gap-1 p-0">
                  <CardTitle class="text-base">Campus Record</CardTitle>
                  <CardDescription>College affiliation and on-campus housing.</CardDescription>
                </CardHeader>
                <div class="grid gap-3 sm:grid-cols-2">
                  <div
                    v-for="field in campusFields"
                    :key="field.key"
                    class="rounded-lg border bg-muted/40 p-3"
                    :class="field.wide ? 'sm:col-span-2' : ''"
                  >
                    <div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                      <component :is="field.icon" class="size-4 shrink-0" />
                      <span>{{ field.label }}</span>
                    </div>
                    <p class="mt-2 break-words text-sm font-medium leading-6">
                      {{ displayValue(identityCard[field.key]) }}
                    </p>
                  </div>
                </div>
              </section>

              <section class="space-y-3">
                <CardHeader class="gap-1 p-0">
                  <CardTitle class="text-base">Personal Details</CardTitle>
                  <CardDescription>Contact and demographic fields from TIS.</CardDescription>
                </CardHeader>
                <div class="grid gap-3 sm:grid-cols-2">
                  <div
                    v-for="field in personalFields"
                    :key="field.key"
                    class="rounded-lg border bg-muted/40 p-3"
                    :class="field.wide ? 'sm:col-span-2' : ''"
                  >
                    <div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                      <component :is="field.icon" class="size-4 shrink-0" />
                      <span>{{ field.label }}</span>
                    </div>
                    <p class="mt-2 break-words text-sm font-medium leading-6">
                      {{ displayValue(identityCard[field.key]) }}
                    </p>
                  </div>
                </div>
              </section>

              <section class="space-y-3">
                <CardHeader class="gap-1 p-0">
                  <CardTitle class="text-base">Interests</CardTitle>
                  <CardDescription>Share topics you care about so Assistant can personalize responses.</CardDescription>
                </CardHeader>
                <div class="rounded-lg border bg-muted/40 p-3">
                  <Label for="profile-interests" class="text-xs font-medium text-muted-foreground">Your interests</Label>
                  <textarea
                    id="profile-interests"
                    v-model="interestDraft"
                    class="mt-2 min-h-24 w-full rounded-md border bg-background px-3 py-2 text-sm"
                    placeholder="e.g. LLM, football, startup"
                    :disabled="interestSaving"
                  />
                  <div class="mt-3 flex flex-wrap items-center gap-3">
                    <Button size="sm" :disabled="interestSaving" @click="saveInterests">
                      {{ interestSaving ? 'Saving...' : 'Save' }}
                    </Button>
                    <p v-if="interestStatus" class="text-xs text-emerald-700">
                      {{ interestStatus }}
                    </p>
                    <p v-if="interestError" class="text-xs text-red-700">
                      {{ interestError }}
                    </p>
                  </div>
                </div>
              </section>
            </CardContent>
          </div>
        </Card>
      </div>
    </main>
  </div>
</template>
