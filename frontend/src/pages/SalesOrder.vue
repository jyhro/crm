<template>
  <div class="flex h-full flex-col overflow-hidden">
    <LayoutHeader>
      <template #left-header>
        <Breadcrumbs :items="breadcrumbs" />
      </template>
      <template v-if="order.data" #right-header>
        <Button
          v-if="order.data.can_delete"
          variant="subtle"
          theme="red"
          :label="__('Eliminar')"
          iconLeft="lucide-trash-2"
          @click="deleteOrder(order.data.name)"
        />
        <Button
          v-if="order.data.can_edit"
          :label="__('Editar')"
          iconLeft="lucide-edit-2"
          @click="showModal = true"
        />
        <Button
          v-if="order.data.can_mark_ready"
          variant="solid"
          :label="__('Marcar como listo')"
          iconLeft="lucide-check"
          @click="markReady(order.data.name)"
        />
      </template>
    </LayoutHeader>
    <div class="flex-1 overflow-y-auto">
      <div
        v-if="order.data"
        class="mx-auto flex max-w-3xl flex-col gap-6 px-5 py-6"
      >
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-2xl font-semibold text-ink-gray-9">
            {{ order.data.name }}
          </h1>
          <Badge
            v-bind="salesOrderState(order.data)"
            variant="subtle"
            size="lg"
          />
        </div>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-4 text-base sm:grid-cols-4">
          <div
            v-for="fact in facts"
            :key="fact.label"
            class="flex min-w-0 flex-col gap-1"
          >
            <dt class="text-sm text-ink-gray-5">{{ fact.label }}</dt>
            <dd class="truncate text-ink-gray-9">
              <router-link
                v-if="fact.route"
                :to="fact.route"
                class="underline decoration-ink-gray-4 underline-offset-2 hover:decoration-ink-gray-7"
              >
                {{ fact.value }}
              </router-link>
              <template v-else>{{ fact.value }}</template>
            </dd>
          </div>
        </dl>
        <div class="overflow-x-auto rounded-6 border">
          <table class="w-full text-base">
            <thead>
              <tr class="border-b text-left text-sm text-ink-gray-5">
                <th class="px-4 py-2 font-normal">{{ __('Producto') }}</th>
                <th class="px-4 py-2 text-right font-normal">
                  {{ __('Cantidad') }}
                </th>
                <th class="px-4 py-2 text-right font-normal">
                  {{ __('Precio') }}
                </th>
                <th class="px-4 py-2 text-right font-normal">
                  {{ __('Importe') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, i) in order.data.items"
                :key="i"
                class="border-b last:border-b-0"
              >
                <td class="px-4 py-3">
                  <div class="font-medium text-ink-gray-9">
                    {{ item.item_name || item.item_code }}
                  </div>
                  <div
                    v-if="item.item_name && item.item_name !== item.item_code"
                    class="text-sm text-ink-gray-5"
                  >
                    {{ item.item_code }}
                  </div>
                </td>
                <td
                  class="whitespace-nowrap px-4 py-3 text-right tabular-nums text-ink-gray-8"
                >
                  {{ item.qty }} {{ item.uom }}
                </td>
                <td
                  class="whitespace-nowrap px-4 py-3 text-right tabular-nums text-ink-gray-8"
                >
                  {{ money(item.rate) }}
                </td>
                <td
                  class="whitespace-nowrap px-4 py-3 text-right tabular-nums text-ink-gray-9"
                >
                  {{ money(item.amount) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="flex flex-col items-end gap-1 px-4 text-base">
          <template v-if="order.data.total_taxes_and_charges">
            <div class="flex gap-6 text-ink-gray-6">
              <span>{{ __('Subtotal') }}</span>
              <span class="tabular-nums">{{ money(order.data.total) }}</span>
            </div>
            <div class="flex gap-6 text-ink-gray-6">
              <span>{{ __('Impuestos') }}</span>
              <span class="tabular-nums">
                {{ money(order.data.total_taxes_and_charges) }}
              </span>
            </div>
          </template>
          <div class="flex gap-6 text-lg font-semibold text-ink-gray-9">
            <span>{{ __('Total') }}</span>
            <span class="tabular-nums">
              {{ money(order.data.grand_total) }}
            </span>
          </div>
        </div>
      </div>
      <div
        v-else-if="order.error"
        class="flex h-full flex-col items-center justify-center gap-3 px-5 text-center"
      >
        <span class="text-lg text-ink-gray-7">
          {{
            order.error.messages?.[0] || __('No se pudo abrir este pedido')
          }}
        </span>
        <Button
          :label="__('Volver a pedidos')"
          :route="{ name: 'Sales Orders' }"
        />
      </div>
      <div
        v-else
        class="flex h-full flex-col items-center justify-center gap-3 text-2xl-medium text-ink-gray-4"
      >
        <LoadingIndicator class="h-6 w-6" />
        <span>{{ __('Cargando…') }}</span>
      </div>
    </div>
  </div>
  <SalesOrderModal
    v-if="showModal"
    v-model:open="showModal"
    :organization="order.data.customer_name || order.data.customer"
    :order-name="order.data.name"
    @saved="order.reload()"
  />
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import SalesOrderModal from '@/components/Modals/SalesOrderModal.vue'
import { useSalesOrderActions } from '@/composables/salesOrders'
import { usersStore } from '@/stores/users'
import { formatDate } from '@/utils'
import { formatCurrency } from '@/utils/numberFormat.js'
import { salesOrderState } from '@/utils/salesOrders'
import {
  Badge,
  Breadcrumbs,
  Button,
  createResource,
  usePageMeta,
} from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  orderId: { type: String, required: true },
})

const router = useRouter()
const { getUser } = usersStore()
const showModal = ref(false)

const order = createResource({
  url: 'crm.ig_extensions.api.orders.get_sales_order_detail',
  makeParams: () => ({ name: props.orderId }),
  auto: true,
})

watch(
  () => props.orderId,
  () => order.reload(),
)

// a deleted order has no page left to show; anything else changes this one
const { deleteOrder, markReady } = useSalesOrderActions((action) =>
  action === 'delete_sales_order'
    ? router.replace({ name: 'Sales Orders' })
    : order.reload(),
)

const breadcrumbs = computed(() => [
  { label: __('Pedidos'), route: { name: 'Sales Orders' } },
  {
    label: props.orderId,
    route: { name: 'Sales Order', params: { orderId: props.orderId } },
  },
])

const facts = computed(() => [
  {
    label: __('Cliente'),
    value: order.data.customer_name || order.data.customer,
    route: order.data.organization && {
      name: 'Organization',
      params: { organizationId: order.data.organization },
    },
  },
  {
    label: __('Fecha del pedido'),
    value: formatDate(order.data.transaction_date, '', true),
  },
  {
    label: __('Fecha de entrega'),
    value: formatDate(order.data.delivery_date, '', true),
  },
  { label: __('Creado por'), value: getUser(order.data.owner).full_name },
])

function money(value) {
  return formatCurrency(value, '', order.data.currency)
}

usePageMeta(() => ({ title: props.orderId }))
</script>
