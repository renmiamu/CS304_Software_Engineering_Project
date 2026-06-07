import type { Component } from 'vue'

export interface NavLink {
  title: string
  description?: string
  path: string
  icon?: Component
  badge?: string
}

export interface NavGroup {
  heading: string
  items: NavMenuItems
}

export interface NavParent {
  title: string
  icon?: Component
  children: NavLink[]
}

export type NavMenuItems = Array<NavLink | NavParent>
