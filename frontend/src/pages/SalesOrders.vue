<template>
  <div class="flex h-full flex-col overflow-hidden">
    <LayoutHeader>
      <template #left-header>
        <Breadcrumbs
          :items="[{ label: __('Pedidos'), route: { name: 'Sales Orders' } }]"
        />
      </template>
      <template #right-header>
        <Button
          :label="__('Actualizar')"
          iconLeft="lucide-refresh-ccw"
          :loading="loading"
          @click="load(true)"
        />
      </template>
    </LayoutHeader>
    <div class="flex-1 overflow-y-auto">
      <div class="ig-page-intro">
        <div><h1>{{ __('Pedidos') }}</h1><p>{{ isManager() ? __('Supervisa los pedidos de tu equipo y su estado.') : __('Consulta y gestiona los pedidos que creaste.') }}</p></div><Button variant="solid" :label="__('Crear pedido')" @click="showChooser = true" />
      </div>
      <OrderFilters @apply="applyFilters" />
      <dl class="ig-order-counts" aria-label="Resumen de resultados">
        <div><dt>{{ __('Resultados') }}</dt><dd>{{ total }}</dd></div>
        <div><dt><span class="ig-dot ig-dot-draft" />{{ __('Borradores') }}</dt><dd>{{ states['0'] || 0 }}</dd></div>
        <div><dt><span class="ig-dot ig-dot-ready" />{{ __('Listos') }}</dt><dd>{{ states['1'] || 0 }}</dd></div>
        <div><dt><span class="ig-dot ig-dot-cancelled" />{{ __('Cancelados') }}</dt><dd>{{ states['2'] || 0 }}</dd></div>
      </dl>
      <div
        v-if="loading && !rows.length"
        class="flex h-full flex-col items-center justify-center gap-3 text-2xl-medium text-ink-gray-4"
      >
        <LoadingIndicator class="h-6 w-6" />
        <span>{{ __('Cargando…') }}</span>
      </div>
      <div
        v-else-if="!rows.length"
        class="flex h-full flex-col items-center justify-center gap-2 px-5 text-center text-ink-gray-5"
      >
        <ErrorMessage v-if="error" :message="error" />
        <template v-else>
          <span class="text-lg">{{ hasFilters ? __('No hay pedidos con estos filtros') : __('Aún no hay pedidos') }}</span>
          <span class="text-base">
            {{
              hasFilters ? __('Cambia los filtros o límpialos para ver más resultados.') : __('Crea uno con «Crear pedido» en la ficha de una organización.')
            }}
          </span>
        </template>
      </div>
      <div v-else class="flex flex-col px-3 py-3 sm:px-10 sm:py-5">
        <ErrorMessage :message="error" />
        <div v-for="(order, i) in rows" :key="order.name">
          <div
            class="group -mx-3 flex items-center gap-2 rounded-4 px-3 py-3 hover:bg-surface-gray-1"
          >
            <router-link
              :to="{ name: 'Sales Order', params: { orderId: order.name } }"
              class="flex min-w-0 flex-1 flex-col gap-2 text-base"
            >
              <div class="flex items-center gap-2">
                <span class="truncate font-medium text-ink-gray-9">
                  {{ order.customer_name || order.customer }}
                </span>
                <Badge
                  v-bind="salesOrderState(order)"
                  variant="subtle"
                  size="sm"
                />
              </div>
              <div class="flex items-center gap-2 truncate text-ink-gray-6">
                <span>{{ order.name }}</span>
                <span class="text-ink-gray-4">·</span>
                <span class="tabular-nums text-ink-gray-8">
                  {{ formatCurrency(order.grand_total, '', order.currency) }}
                </span>
                <span class="text-ink-gray-4">·</span>
                <span>{{ formatDate(order.transaction_date, '', true) }}</span>
                <template v-if="isManager()">
                  <span class="text-ink-gray-4">·</span>
                  <span class="truncate">
                    {{ getUser(order.owner).full_name }}
                  </span>
                </template>
              </div>
            </router-link>
            <Button
              v-if="order.docstatus === 0"
              variant="subtle"
              class="hidden sm:flex"
              :label="__('Marcar como listo')"
              iconLeft="lucide-check"
              @click="markReady(order.name)"
            />
            <Dropdown :options="rowActions(order)">
              <Button
                icon="lucide-more-horizontal"
                variant="ghost"
                :aria-label="__('Acciones')"
              />
            </Dropdown>
          </div>
          <div
            v-if="i < rows.length - 1"
            class="h-px border-t border-outline-elevation-2"
          />
        </div>
        <div v-if="hasMore" class="flex justify-center py-4">
          <Button
            :label="__('Cargar más')"
            :loading="loading"
            @click="load()"
          />
        </div>
      </div>
    </div>
  </div>
  <SalesOrderModal
    v-if="showModal"
    v-model:open="showModal"
    :organization="editing.customer_name || editing.customer"
    :order-name="editing.name"
    @saved="load(true)"
  />
  <Dialog v-model="showChooser" :title="__('Crear pedido para un cliente')"><Link v-model="selectedOrganization" doctype="CRM Organization" :label="__('Cliente de tu cartera')" :placeholder="__('Seleccionar cliente')" /><template #actions><div class="flex justify-end gap-2"><Button :label="__('Cancelar')" @click="showChooser = false" /><Button variant="solid" :label="__('Continuar')" :disabled="!selectedOrganization" @click="newOrder" /></div></template></Dialog>
</template>

<script setup>
import LoadingIndicator from '@/components/Icons/LoadingIndicator.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import SalesOrderModal from '@/components/Modals/SalesOrderModal.vue'
import OrderFilters from '@/components/ListViews/OrderFilters.vue'
import Link from '@/components/Controls/Link.vue'
import { useSalesOrderActions } from '@/composables/salesOrders'
import { usersStore } from '@/stores/users'
import { formatDate } from '@/utils'
import { formatCurrency } from '@/utils/numberFormat.js'
import { salesOrderState } from '@/utils/salesOrders'
import {
  Badge,
  Breadcrumbs,
  Button,
  Dropdown,
  Dialog,
  ErrorMessage,
  call,
  usePageMeta,
} from 'frappe-ui'
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const PAGE_SIZE = 50

const router = useRouter()
const route = useRoute()
const { getUser, isManager } = usersStore()

const rows = ref([])
const hasMore = ref(false)
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editing = ref(null)
const showChooser = ref(false)
const selectedOrganization = ref('')
function newOrder() { editing.value = { name: '', customer_name: selectedOrganization.value }; showChooser.value = false; showModal.value = true }
const total = ref(0)
const states = ref({})
const appliedFilters = ref({})
const hasFilters = computed(() => Object.values(appliedFilters.value).some(Boolean))
let requestVersion = 0

function applyFilters(filters) {
  appliedFilters.value = filters
  load(true)
}

// reset: start over from the newest order; otherwise append the next page
async function load(reset = false) {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  try {
    const page = await call(
      'crm.ig_extensions.api.sales_orders.get_page',
      { ...appliedFilters.value, limit: PAGE_SIZE, start: reset ? 0 : rows.value.length },
    )
    if (version !== requestVersion) return
    rows.value = reset ? page.rows : [...rows.value, ...page.rows]
    total.value = page.total
    states.value = page.states
    hasMore.value = rows.value.length < page.total
  } catch (exception) {
    if (version !== requestVersion) return
    error.value =
      exception?.messages?.[0] ||
      exception?.message ||
      __('No se pudieron cargar los pedidos')
  } finally {
    if (version === requestVersion) loading.value = false
  }
}

const { deleteOrder, markReady } = useSalesOrderActions(() => load(true))

function editOrder(order) {
  editing.value = order
  showModal.value = true
}

function rowActions(order) {
  const actions = [
    {
      label: __('Ver detalle'),
      icon: 'lucide-eye',
      onClick: () =>
        router.push({ name: 'Sales Order', params: { orderId: order.name } }),
    },
  ]
  if (order.docstatus === 0) {
    actions.push(
      {
        label: __('Editar'),
        icon: 'lucide-edit-2',
        onClick: () => editOrder(order),
      },
      {
        label: __('Marcar como listo'),
        icon: 'lucide-check',
        onClick: () => markReady(order.name),
      },
      {
        label: __('Eliminar'),
        icon: 'lucide-trash-2',
        onClick: () => deleteOrder(order.name),
      },
    )
  }
  return actions
}

onMounted(() => {
  if (route.query.organization) {
    selectedOrganization.value = String(route.query.organization)
    showChooser.value = true
  }
  load(true)
})

usePageMeta(() => ({ title: __('Pedidos') }))
</script>
