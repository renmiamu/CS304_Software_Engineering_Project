// https://nuxt.com/docs/api/configuration/nuxt-config

import tailwindcss from '@tailwindcss/vite'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  css: ['~/assets/css/tailwind.css'],
  modules: [
    '@nuxtjs/color-mode',
    '@nuxt/icon',
  ],
  colorMode: {
    classSuffix: '',
    preference: 'light',
    fallback: 'light',
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? 'http://localhost:9000',
      cookiesFile: process.env.NUXT_PUBLIC_COOKIES_FILE ?? '',
    },
  },
  components: [
    {
      path: '~/components',
      extensions: ['vue'],
    },
  ],
  vite: {
    plugins: [tailwindcss()],
  },
})
