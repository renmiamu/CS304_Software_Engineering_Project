import {
  IconBook2,
  IconBrain,
  IconCalendarEvent,
  IconLayoutDashboard,
  IconLink,
  IconMail,
  IconUserCircle,
} from '@tabler/icons-vue'
import type { NavGroup, NavLink, NavMenuItems, NavParent } from '~/types/nav'

export const appNavigationMenu: NavGroup[] = [
  {
    heading: 'General',
    items: [
      {
        title: 'Dashboard',
        description: 'Today schedule, near-term deadlines, and source health.',
        path: '/dashboard',
        icon: IconLayoutDashboard,
      },
      {
        title: 'Schedule',
        description: 'Courses, deadline timeline, and conflict handling.',
        path: '/schedule',
        icon: IconCalendarEvent,
      },
      {
        title: 'Assistant',
        description: 'Main AI workspace with real chat history and Fast / Thinking switching.',
        path: '/assistant',
        icon: IconBrain,
      },
    ],
  },
  {
    heading: 'Workspace',
    items: [
      {
        title: 'Integrations',
        description: 'Connection health, sync jobs, and diagnostics.',
        path: '/sources',
        icon: IconLink,
      },
      {
        title: 'Mail',
        description: 'Mailbox inbox, message detail, and compose workspace.',
        path: '/mail',
        icon: IconMail,
      },
      {
        title: 'Blackboard',
        description: 'BB course files, grades, and upcoming deadlines.',
        path: '/blackboard',
        icon: IconBook2,
      },
      {
        title: 'Profile',
        description: 'Read-only campus identity from connected school records.',
        path: '/profile',
        icon: IconUserCircle,
      },
    ],
  },
]

function flattenItems(items: NavMenuItems): NavLink[] {
  return items.flatMap((item) => {
    if ('children' in item) {
      return (item as NavParent).children
    }

    return item as NavLink
  })
}

export const appNavigationItems = appNavigationMenu.flatMap(group => flattenItems(group.items))

export function getPageMeta(path: string) {
  return appNavigationItems.find(item => path === item.path || path.startsWith(`${item.path}/`))
}
