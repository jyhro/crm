<template>
  <div class="flex h-full flex-col">
    <div
      v-if="orders.loading && !orders.fetched"
      class="flex flex-1 flex-col items-center justify-center gap-3 text-2xl-medium text-ink-gray-4"
    >
      <LoadingIndicator class="h-6 w-6" />
      <span>{{ __('Loading...') }}</span>
    </div>
    <div v-else-if="!rows.length" class="flex flex-1 flex-col items-center justify-center text-ink-gray-5">
      <span class="text-lg">{{ __('No sales orders yet') }}</span>
    </div>
    <div v-else class="flex flex-col px-3 pb-3 sm:px-10 sm:pb-5">
      <div v-for="(order, i) in rows" :key="order.name">
        <div class="group -mx-3 flex items-center gap-2 rounded-4 px-3 py-3 hover:bg-surface-gray-1">
          <router-link
            :to="{ name: 'Sales Order', params: { orderId: order.name } }"
            class="flex min-w-0 flex-1 cursor-pointer items-center gap-4"
          >
            <div class="flex min-w-0 flex-1 flex-col gap-2 truncate text-base">
              <div class="flex items-center gap-2">
                <span class="truncate font-medium text-ink-gray-9">{{ order.name }}</span>
                <Badge v-bind="salesOrderState(order)" variant="subtle" size="sm" />
              </div>
              <div class="flex items-center gap-2 text-ink-gray-6">
                <span class="tabular-nums text-ink-gray-8">
                  {{ formatCurrency(order.grand_total, '', order.currency) }}
                </span>
                <span class="text-ink-gray-4">·</span>
                <span>{{ formatDate(order.transaction_date || order.delivery_date) }}</span>
              </div>
            </div>
          </router-link>
          <Button
            v-if="order.docstatus === 0"
            variant="subtle"
            :label="__('Edit draft')"
            @click.stop="$emit('edit', order)"
          />
        </div>
        <div v-if="i < rows.length - 1" class="h-px border-t border-outline-elevation-2" />
      </div>
    </div>
  </div>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import { formatDate } from '@/utils'
import { formatCurrency } from '@/utils/numberFormat.js'
import { salesOrderState } from '@/utils/salesOrders'
import { Badge, Button, createResource } from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  organization: { type: String, required: true },
})

defineEmits(['edit'])

const orders = createResource({
  url: 'crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.get_organization_sales_orders',
  params: { organization: props.organization },
  auto: true,
})

const rows = computed(() => orders.data || [])

function reload() {
  orders.reload()
}

defineExpose({ reload })
</script>
