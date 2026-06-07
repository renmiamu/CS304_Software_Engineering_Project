<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  description: string
}>()
</script>

<template>
  <div class="rounded-3xl border border-border/80 bg-card/90 p-5 shadow-sm">
    <p class="text-sm text-muted-foreground">{{ title }}</p>
    <p class="mt-3 text-3xl font-semibold tracking-tight text-foreground">{{ value }}</p>
    <p class="mt-2 text-sm leading-6 text-muted-foreground">{{ description }}</p>
  </div>
</template>
