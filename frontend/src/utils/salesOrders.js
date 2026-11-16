// How the CRM words an ERPNext Sales Order: a ready order is a submitted one.
export function salesOrderState(order) {
  if (order?.docstatus === 2) return { label: __('Cancelado'), theme: 'red' }
  if (order?.docstatus === 1) return { label: __('Listo'), theme: 'green' }
  return { label: __('Borrador'), theme: 'orange' }
}
