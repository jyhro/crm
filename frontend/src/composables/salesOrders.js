import { globalStore } from '@/stores/global.js'
import { call, toast } from 'frappe-ui'

const API = 'crm.ig_extensions.api.orders.'

// Confirmed "delete" and "mark as ready" for a draft order.
// `onDone(action, name)` runs once the server has accepted either one.
export function useSalesOrderActions(onDone) {
  const { $dialog } = globalStore()

  function confirm(action, name, { title, message, label, theme, success }) {
    $dialog({
      title,
      message,
      actions: [
        {
          label,
          theme,
          variant: 'solid',
          onClick: async ({ close }) => {
            try {
              await call(API + action, { name })
              toast.success(success)
              onDone?.(action, name)
            } catch (exception) {
              toast.error(
                exception?.messages?.[0] ||
                  exception?.message ||
                  __('No se pudo completar la acción'),
              )
            }
            close()
          },
        },
      ],
    })
  }

  function deleteOrder(name) {
    confirm('delete_sales_order', name, {
      title: __('Eliminar pedido'),
      message: __(
        '¿Eliminar el pedido {0}? Esta acción no se puede deshacer.',
        [name],
      ),
      label: __('Eliminar'),
      theme: 'red',
      success: __('Pedido eliminado'),
    })
  }

  function markReady(name) {
    confirm('mark_sales_order_ready', name, {
      title: __('Marcar como listo'),
      message: __(
        '¿Marcar el pedido {0} como listo? Después ya no se podrá editar ni eliminar.',
        [name],
      ),
      label: __('Marcar como listo'),
      success: __('Pedido marcado como listo'),
    })
  }

  return { deleteOrder, markReady }
}
