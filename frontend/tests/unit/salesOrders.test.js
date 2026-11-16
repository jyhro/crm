import { salesOrderState } from '@/utils/salesOrders'

describe('salesOrderState', () => {
  it('shows a draft order as still open', () => {
    expect(salesOrderState({ docstatus: 0, status: 'Draft' })).toEqual({
      label: 'Borrador',
      theme: 'orange',
    })
  })

  it('shows a submitted order as ready, whatever its ERPNext status', () => {
    expect(
      salesOrderState({ docstatus: 1, status: 'To Deliver and Bill' }),
    ).toEqual({ label: 'Listo', theme: 'green' })
  })

  it('shows a cancelled order as cancelled', () => {
    expect(salesOrderState({ docstatus: 2, status: 'Cancelled' })).toEqual({
      label: 'Cancelado',
      theme: 'red',
    })
  })
})
