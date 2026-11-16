<template>
  <form class="ig-filter-panel" @submit.prevent="$emit('apply', { ...filters })">
    <div class="ig-filter-grid">
      <label>{{ __('Desde') }}<input v-model="filters.from_date" type="date" class="form-input" /></label>
      <label>{{ __('Hasta') }}<input v-model="filters.to_date" type="date" class="form-input" /></label>
      <label>{{ __('Número de pedido') }}<input v-model="filters.order_id" type="search" class="form-input" :placeholder="__('Buscar por identificador')" /></label>
      <div><label id="order-customer-label">{{ __('Cliente') }}</label><Autocomplete v-model="filters.customer" aria-labelledby="order-customer-label" :options="customers" :placeholder="__('Todos mis clientes')" :filterable="false" @update:query="customerSearch = $event" /></div>
      <div><label id="order-product-label">{{ __('Producto incluido') }}</label><Autocomplete v-model="filters.item_code" aria-labelledby="order-product-label" :options="products" :placeholder="__('Todos los productos')" :filterable="false" @update:query="productSearch = $event" /></div>
      <label>{{ __('Estado') }}<select v-model="filters.status" class="form-select"><option value="">{{ __('Todos los estados') }}</option><option value="draft">{{ __('Borrador') }}</option><option value="ready">{{ __('Listo') }}</option><option value="cancelled">{{ __('Cancelado') }}</option></select></label>
    </div>
    <div class="flex flex-wrap items-center justify-between gap-3 pt-4">
      <span class="text-sm text-ink-gray-6">{{ __('El período corresponde a la fecha del pedido.') }}</span>
      <div class="flex gap-2"><Button :label="__('Limpiar')" @click="clear" /><Button type="submit" variant="solid" :label="__('Aplicar filtros')" /></div>
    </div>
  </form>
</template>

<script setup>
import Autocomplete from '@/components/frappe-ui/Autocomplete.vue'
import { Button, call } from 'frappe-ui'
import { onMounted, reactive, ref } from 'vue'
import { watchDebounced } from '@vueuse/core'

const emit = defineEmits(['apply'])
const filters = reactive({ from_date: '', to_date: '', order_id: '', customer: '', item_code: '', status: '' })
const customers = ref([])
const products = ref([])
const customerSearch = ref('')
const productSearch = ref('')
async function options(field, txt, target) {
  try { target.value = await call('crm.ig_extensions.api.sales_orders.get_filter_options', { field, txt }) }
  catch { target.value = [] }
}
watchDebounced(customerSearch, (txt) => options('customer', txt, customers), { debounce: 250 })
watchDebounced(productSearch, (txt) => options('item_code', txt, products), { debounce: 250 })
function clear() {
  Object.keys(filters).forEach((key) => { filters[key] = '' })
  emit('apply', { ...filters })
}
onMounted(() => { options('customer', '', customers); options('item_code', '', products) })
</script>
