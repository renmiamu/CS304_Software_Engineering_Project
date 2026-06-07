<script setup lang="ts">
import { AccordionTrigger } from 'reka-ui'
import { ChevronDown } from 'lucide-vue-next'
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <AccordionTrigger
    :class="
      cn(
        'flex flex-1 items-center justify-between py-3 text-sm font-medium transition-all hover:underline [&[data-state=open]>svg]:rotate-180',
        props.class,
      )
    "
  >
    <slot />
    <ChevronDown class="size-4 shrink-0 text-muted-foreground transition-transform duration-200" />
  </AccordionTrigger>
</template>
