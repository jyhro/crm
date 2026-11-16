<template>
  <div class="flex h-full min-w-0 flex-col overflow-hidden">
    <LayoutHeader><template #left-header><Breadcrumbs :items="[{ label: __('Productos'), route: { name: 'Products' } }]" /></template></LayoutHeader>
    <div class="flex-1 overflow-y-auto">
      <div class="ig-page-intro"><div><h1>{{ __('Productos') }}</h1><p>{{ __('Catálogo de materiales y suministros para tu gestión comercial.') }}</p></div><span class="ig-total">{{ total }} {{ __('productos') }}</span></div>
      <form class="ig-catalog-search" @submit.prevent="load(true)"><label for="product-search">{{ __('Buscar en el catálogo') }}</label><div class="flex gap-2"><input id="product-search" v-model="search" type="search" class="form-input min-w-0 flex-1" :placeholder="__('Nombre o código del producto')" /><Button type="submit" :label="__('Buscar')" :loading="loading" /></div></form>
      <ErrorMessage v-if="error" :message="error" class="mx-5 my-4" />
      <div v-if="loading && !rows.length" class="ig-empty" role="status">{{ __('Cargando catálogo…') }}</div>
      <div v-else-if="!rows.length && !error" class="ig-empty"><h2>{{ __('No hay productos para mostrar') }}</h2><p>{{ search ? __('Prueba otro nombre o código.') : __('Aquí aparecerán los productos de venta activos de ERPNext.') }}</p></div>
      <div v-else class="ig-product-list">
        <router-link v-for="item in rows" :key="item.name" :to="{ name: 'Product', params: { productId: item.name } }" class="ig-product-row">
          <div class="min-w-0"><span class="text-sm text-ink-gray-6">{{ item.item_code }}</span><h2>{{ item.item_name }}</h2><p>{{ item.item_group }}</p></div>
          <span class="ig-product-unit">{{ item.stock?.status === 'known' ? `${item.stock.actual_qty} ${item.stock_uom}` : item.stock?.status === 'not_stock' ? __('No inventariable') : item.stock?.status === 'restricted' ? __('Stock restringido') : __('Stock sin registro') }}</span><span class="lucide-chevron-right size-4 shrink-0 text-ink-gray-5" aria-hidden="true" />
        </router-link>
      </div>
      <div v-if="rows.length < total" class="flex justify-center py-5"><Button :label="__('Cargar más')" :loading="loading" @click="load()" /></div>
    </div>
  </div>
</template>
<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import { Breadcrumbs, Button, ErrorMessage, call, usePageMeta } from 'frappe-ui'
import { onMounted, ref } from 'vue'
const search = ref(''), rows = ref([]), total = ref(0), loading = ref(false), error = ref('')
let version = 0
async function load(reset = false) {
  const id = ++version
  loading.value = true; error.value = ''
  try {
    const page = await call('crm.ig_extensions.api.workspace.get_products', { txt: search.value, start: reset ? 0 : rows.value.length })
    if (id !== version) return
    rows.value = reset ? page.rows : [...rows.value, ...page.rows]; total.value = page.total
  } catch (e) { if (id === version) error.value = e.messages?.[0] || __('No se pudo cargar el catálogo. Vuelve a intentarlo.') }
  finally { if (id === version) loading.value = false }
}
onMounted(() => load(true))
usePageMeta(() => ({ title: __('Productos') }))
</script>
