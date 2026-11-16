<template>
  <div class="flex h-full min-w-0 flex-col overflow-hidden">
    <LayoutHeader><template #left-header><Breadcrumbs :items="[{ label: __('Productos'), route: { name: 'Products' } }, { label: productId }]" /></template></LayoutHeader>
    <div class="flex-1 overflow-y-auto">
      <div v-if="product.data" class="ig-product-detail">
        <span class="text-base text-ink-gray-6">{{ product.data.item_code }}</span><h1>{{ product.data.item_name }}</h1>
        <dl class="ig-product-facts"><div><dt>{{ __('Grupo') }}</dt><dd>{{ product.data.item_group }}</dd></div><div><dt>{{ __('Unidad') }}</dt><dd>{{ product.data.stock_uom }}</dd></div><div><dt>{{ __('Inventariable') }}</dt><dd>{{ product.data.is_stock_item ? __('Sí') : __('No') }}</dd></div><div><dt>{{ __('Estado') }}</dt><dd>{{ product.data.disabled ? __('Inactivo') : __('Activo') }}</dd></div></dl>
        <h2>{{ __('Existencias por almacén') }}</h2><p class="text-sm text-ink-gray-6">{{ __('Cantidades registradas en ERPNext, en la unidad de inventario. No confirman sincronización con Profit.') }}</p>
        <div v-if="product.data.stock?.status === 'known'" class="overflow-x-auto"><table class="ig-table"><thead><tr><th>{{ __('Almacén') }}</th><th>{{ __('Existencia física') }}</th><th>{{ __('Reservado para ventas') }}</th><th>{{ __('Actualización') }}</th></tr></thead><tbody><tr v-for="stock in product.data.stock.warehouses" :key="stock.warehouse"><td>{{ stock.warehouse }}</td><td>{{ stock.actual_qty }} {{ product.data.stock.uom }}</td><td>{{ stock.reserved_qty }} {{ product.data.stock.uom }}</td><td>{{ stock.modified }}</td></tr></tbody></table></div>
        <p v-else class="ig-empty">{{ product.data.stock?.status === 'not_stock' ? __('Este producto no controla inventario.') : product.data.stock?.status === 'restricted' ? __('Tu rol no tiene permiso para consultar existencias.') : __('Sin registros de existencias en almacenes visibles. Esto no significa stock cero.') }}</p>
        <h2>{{ __('Descripción') }}</h2><p class="whitespace-pre-line text-p-base text-ink-gray-7">{{ description || __('Este producto aún no tiene una descripción registrada.') }}</p>
        <h2>{{ __('Precios de venta registrados') }}</h2>
        <p class="text-sm text-ink-gray-6">{{ __('La vigencia y las reglas comerciales se validan al preparar el pedido.') }}</p>
        <div v-if="product.data.prices.length" class="overflow-x-auto"><table class="ig-table"><thead><tr><th>{{ __('Lista') }}</th><th>{{ __('Precio') }}</th><th>{{ __('Vigencia') }}</th></tr></thead><tbody><tr v-for="(price, i) in product.data.prices" :key="i"><td>{{ price.price_list }}</td><td class="whitespace-nowrap tabular-nums">{{ formatCurrency(price.price_list_rate, '', price.currency) }}<span class="text-sm text-ink-gray-6"> / {{ price.uom || product.data.stock_uom }}</span></td><td>{{ price.valid_from || '—' }} → {{ price.valid_upto || __('Sin fecha final') }}</td></tr></tbody></table></div>
        <p v-else class="ig-empty">{{ __('No hay precios de venta registrados o visibles para tu rol.') }}</p>
        <Button :route="{ name: 'Sales Orders' }" :label="__('Ver pedidos')" />
      </div>
      <div v-else class="ig-empty" role="status">{{ product.error ? (product.error.messages?.[0] || __('No se pudo abrir el producto.')) : __('Cargando producto…') }}</div>
    </div>
  </div>
</template>
<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import { Breadcrumbs, Button, createResource, usePageMeta } from 'frappe-ui'
import { formatCurrency } from '@/utils/numberFormat.js'
import { computed } from 'vue'
const props = defineProps({ productId: { type: String, required: true } })
const product = createResource({ url: 'crm.ig_extensions.api.workspace.get_product', params: { name: props.productId }, auto: true })
const description = computed(() => {
  const parser = new DOMParser()
  return parser.parseFromString(product.data?.description || '', 'text/html').body.textContent || ''
})
usePageMeta(() => ({ title: product.data?.item_name || props.productId }))
</script>
