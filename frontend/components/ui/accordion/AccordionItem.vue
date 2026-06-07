<script setup lang="ts">
import { AccordionItem } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{
  value: string
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <AccordionItem
    :value="value"
    :class="cn('border-b', props.class)"
  >
    <slot />
  </AccordionItem>
</template>
