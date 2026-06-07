<script setup lang="ts">
const colorMode = useColorMode()
const color = computed(() => (colorMode.value === 'dark' ? '#D29054' : '#EC6C00'))
const { theme } = useAppSettings()

useHead({
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color },
  ],
  htmlAttrs: {
    lang: 'en',
  },
  bodyAttrs: {
    class: computed(() => `color-${theme.value.color} theme-${theme.value.type}`),
  },
})
</script>

<template>
  <Body class="overscroll-none antialiased bg-background text-foreground">
    <NuxtRouteAnnouncer />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </Body>
</template>
