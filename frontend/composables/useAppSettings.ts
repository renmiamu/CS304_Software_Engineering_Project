import type { AppSettings } from '~/types/app-settings'
import { THEME_TYPES, type ThemeColor, type ThemeType } from '~/constants/themes'

const defaultAppSettings: Required<AppSettings> = {
  sidebar: {
    collapsible: 'offcanvas',
    side: 'left',
    variant: 'inset',
  },
  theme: {
    color: 'orange',
    type: 'scaled',
  },
}

const BRAND_THEME_COLOR: ThemeColor = 'orange'

function isThemeType(value: unknown): value is ThemeType {
  return typeof value === 'string' && (THEME_TYPES as readonly string[]).includes(value)
}

function mergeSettings(base: AppSettings, override?: AppSettings): Required<AppSettings> {
  const mergedTheme = {
    ...defaultAppSettings.theme,
    ...(base.theme ?? {}),
    ...(override?.theme ?? {}),
  }

  return {
    sidebar: {
      ...defaultAppSettings.sidebar,
      ...(base.sidebar ?? {}),
      ...(override?.sidebar ?? {}),
    },
    theme: {
      color: BRAND_THEME_COLOR,
      type: isThemeType(mergedTheme.type) ? mergedTheme.type : defaultAppSettings.theme.type,
    },
  }
}

export function useAppSettings() {
  const { appSettings } = useAppConfig()
  const configured = mergeSettings(defaultAppSettings, appSettings as AppSettings | undefined)

  const cookieSettings = useCookie<Required<AppSettings>>('app_settings', {
    default: () => configured,
    sameSite: 'lax',
  })

  // Normalize old cookie values so previous multi-theme selections converge to brand orange.
  cookieSettings.value = mergeSettings(configured, cookieSettings.value)

  const updateAppSettings = (nextSettings: AppSettings) => {
    cookieSettings.value = mergeSettings(cookieSettings.value, nextSettings)
  }

  return {
    updateAppSettings,
    sidebar: computed(() => cookieSettings.value.sidebar),
    theme: computed(() => cookieSettings.value.theme),
  }
}
