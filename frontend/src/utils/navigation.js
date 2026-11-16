import ContactsIcon from '@/components/Icons/ContactsIcon.vue'
import DealsIcon from '@/components/Icons/DealsIcon.vue'
import LeadsIcon from '@/components/Icons/LeadsIcon.vue'
import NoteIcon from '@/components/Icons/NoteIcon.vue'
import OrganizationsIcon from '@/components/Icons/OrganizationsIcon.vue'
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import TaskIcon from '@/components/Icons/TaskIcon.vue'
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucideShoppingCart from '~icons/lucide/shopping-cart'
import LucidePackage from '~icons/lucide/package'
import router from '@/router'

export const navigationItems = [
  {
    label: 'Reportes',
    icon: LucideLayoutDashboard,
    route: 'Dashboard',
  },
  { label: 'Leads', icon: LeadsIcon, route: 'Leads' },
  { label: 'Deals', icon: DealsIcon, route: 'Deals' },
  { label: 'Contacts', icon: ContactsIcon, route: 'Contacts' },
  { label: 'Clientes', icon: OrganizationsIcon, route: 'Organizations' },
  { label: 'Pedidos', icon: LucideShoppingCart, route: 'Sales Orders' },
  { label: 'Productos', icon: LucidePackage, route: 'Products' },
  { label: 'Notes', icon: NoteIcon, route: 'Notes' },
  { label: 'Tasks', icon: TaskIcon, route: 'Tasks' },
  { label: 'Call Logs', icon: PhoneIcon, route: 'Call Logs' },
]

export function getNavigationItems({ mobile = false } = {}) {
  return navigationItems.filter(
    (item) => router.hasRoute(item.route) && (!mobile || !item.desktopOnly),
  )
}
