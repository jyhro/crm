import { getNavigationItems, navigationItems } from '@/utils/navigation'

describe('navigationItems', () => {
  it('uses unique route names', () => {
    const routes = navigationItems.map((item) => item.route)
    expect(new Set(routes).size).toBe(routes.length)
  })

  it('omits desktop-only destinations on mobile', () => {
    const mobileRoutes = getNavigationItems({ mobile: true }).map(
      (item) => item.route,
    )
    expect(mobileRoutes).toContain('Dashboard')
    expect(mobileRoutes).not.toContain('Calendar')
    expect(mobileRoutes).toContain('Leads')
    expect(mobileRoutes).toContain('Products')
  })

  it('offers the orders page, on mobile too', () => {
    const orders = getNavigationItems({ mobile: true }).find(
      (item) => item.route === 'Sales Orders',
    )
    expect(orders?.label).toBe('Pedidos')
  })
})
