<template>
  <div class="flex h-full min-w-0 flex-col overflow-hidden">
    <LayoutHeader><template #left-header><Breadcrumbs :items="[{ label: __('Reportes'), route: { name: 'Dashboard' } }]" /></template><template #right-header><Button :label="__('Actualizar')" iconLeft="lucide-refresh-ccw" :loading="overview.loading" @click="overview.reload()" /></template></LayoutHeader>
    <div class="flex-1 overflow-y-auto" :aria-busy="overview.loading">
      <div class="ig-page-intro"><div><h1>{{ __('Tu actividad comercial, en un solo lugar.') }}</h1><p>{{ __('Llamadas registradas, pedidos y cartera de clientes de International Graphics.') }}</p></div></div>
      <form class="ig-report-filters" @submit.prevent="overview.reload()">
        <label>{{ __('Desde') }}<input v-model="filters.from_date" type="date" class="form-input" required /></label>
        <label>{{ __('Hasta') }}<input v-model="filters.to_date" type="date" class="form-input" required /></label>
        <label v-if="isManager()">{{ __('Vendedor') }}<select v-model="filters.user" class="form-select"><option value="">{{ __('Todo el equipo autorizado') }}</option><option v-for="seller in sellers.data || []" :key="seller.value" :value="seller.value">{{ seller.label }}</option></select></label>
        <Button type="submit" variant="solid" :label="__('Ver reporte')" :loading="overview.loading" />
      </form>
      <ErrorMessage v-if="overview.error" :message="overview.error.messages?.[0] || __('No se pudo cargar el reporte. Vuelve a intentarlo.')" class="mx-5 my-4" />
      <div v-if="!overview.data && overview.loading" class="ig-empty" role="status">{{ __('Consultando la actividad registrada…') }}</div>
      <template v-if="overview.data">
        <p class="ig-report-caption">{{ overview.data.from_date }} — {{ overview.data.to_date }} · {{ __('Según los permisos de tu cuenta') }}</p>
        <dl class="ig-order-counts ig-overview-counts">
          <div><dt>{{ __('Llamadas registradas') }}</dt><dd>{{ overview.data.calls }}</dd><p>{{ overview.data.completed }} {{ __('completadas') }} · {{ duration(overview.data.duration) }}</p></div>
          <div><dt>{{ __('Pedidos') }}</dt><dd>{{ overview.data.orders }}</dd><p>{{ __('Creados en el período') }}</p></div>
          <div><dt>{{ __('Clientes de la cartera') }}</dt><dd>{{ overview.data.customers }}</dd><p>{{ __('Cartera actual visible, sin filtro de fecha') }}</p></div>
          <div><dt>{{ __('Productos del catálogo') }}</dt><dd>{{ overview.data.catalog_products }}</dd><p>{{ __('Productos de venta activos y visibles') }}</p></div>
        </dl>
        <div class="ig-report-grid">
          <section class="ig-panel"><h2>{{ __('Resultados comerciales de llamadas') }}</h2><p>{{ __('Disposición registrada por el vendedor, independiente del estado técnico del proveedor.') }}</p><div v-if="overview.data.outcomes?.length" class="ig-chart"><DonutChart :data="overview.data.outcomes" category="label" value="count" :showDataLabels="true" :palette="['#ed1b24', '#6d6e72', '#b77917', '#248344', '#497b95', '#a0754f']" /></div><div v-else class="ig-empty">{{ __('No hay llamadas para mostrar resultados en este período.') }}</div><ul class="ig-outcome-legend"><li v-for="outcome in overview.data.outcomes || []" :key="outcome.label"><span>{{ outcome.label }}</span><strong>{{ outcome.count }} · {{ Math.round(outcome.count / Math.max(overview.data.calls, 1) * 1000) / 10 }}%</strong></li></ul><p>{{ __('Sin resultado comercial registrado no equivale a llamada fallida.') }}</p></section>
          <section class="ig-panel ig-report-wide"><h2>{{ __('Evolución de pedidos') }}</h2><p>{{ __('Número de pedidos por fecha, dentro del período seleccionado.') }}</p><div v-if="overview.data.trend.length" class="ig-chart"><LineChart :data="overview.data.trend" x="transaction_date" :y="['count']" :seriesConfig="{ count: { label: __('Pedidos'), color: '#ed1b24' } }" :xAxis="{ type: 'time', timeGrain: 'day' }" /></div><div v-else class="ig-empty"><span class="lucide-shopping-cart size-6 text-ink-gray-5" aria-hidden="true" /><span>{{ __('No hay pedidos registrados en este período.') }}</span><Button :route="{ name: 'Organizations' }" :label="__('Ver clientes')" /></div></section>
          <section class="ig-panel"><h2>{{ __('Estado de los pedidos') }}</h2><p>{{ __('«Listo» indica un pedido validado en ERPNext; no confirma su envío a Profit.') }}</p><ul class="ig-bar-list"><li v-for="state in orderStates" :key="state.key"><div><span><span class="ig-dot" :class="state.dot" />{{ state.label }}</span><strong>{{ overview.data.states[state.key] || 0 }}</strong></div><meter min="0" :max="Math.max(overview.data.orders, 1)" :value="overview.data.states[state.key] || 0" :aria-label="state.label" /></li></ul><Button :route="{ name: 'Sales Orders' }" :label="__('Explorar pedidos')" /></section>
          <section class="ig-panel ig-report-wide"><h2>{{ __('Llamadas por vendedor') }}</h2><p>{{ __('Registros disponibles en el CRM. «Completada» es el estado del registro, no una confirmación de conversación humana.') }}</p><ul v-if="overview.data.agents.length" class="ig-bar-list"><li v-for="agent in overview.data.agents" :key="agent.user"><div><span>{{ agent.label }}</span><strong>{{ agent.calls }}</strong></div><meter min="0" :max="maxCalls" :value="agent.calls" :aria-label="__('Llamadas de {0}', [agent.label])" /><small>{{ agent.completed }} {{ __('completadas') }} · {{ duration(agent.duration) }} {{ __('registrados') }}</small></li></ul><div v-else class="ig-empty">{{ __('No hay llamadas registradas para este período y equipo.') }}</div><Button :route="{ name: 'Call Logs' }" :label="__('Ver registros de llamadas')" /></section>
          <section class="ig-panel"><h2>{{ __('Productos en los pedidos') }}</h2><p>{{ __('Unidades solicitadas por producto y unidad de medida en los pedidos visibles.') }}</p><ul v-if="overview.data.products.length" class="ig-ranked-list"><li v-for="item in overview.data.products" :key="item.item_code + item.uom"><router-link :to="{ name: 'Product', params: { productId: item.item_code } }">{{ item.item_name || item.item_code }}</router-link><strong>{{ item.qty }} <small>{{ item.uom }}</small></strong></li></ul><div v-else class="ig-empty">{{ __('Los productos aparecerán aquí cuando haya pedidos en el período.') }}</div><Button :route="{ name: 'Products' }" :label="__('Abrir catálogo')" /></section>
        </div>
        <div class="ig-report-footnote"><p>{{ __('Solo se incluyen llamadas almacenadas en el CRM. La captura automática y el audio dependen del proveedor telefónico y de su configuración.') }}</p><Button v-if="isAdmin()" :route="{ name: 'Dashboard Advanced' }" :label="__('Gráficos avanzados')" variant="ghost" /></div>
      </template>
    </div>
  </div>
</template>
<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import { Breadcrumbs, Button, ErrorMessage, createResource, dayjs, usePageMeta } from 'frappe-ui'
import { LineChart, DonutChart } from 'frappe-ui/charts'
import { computed, reactive } from 'vue'
import { usersStore } from '@/stores/users'
const { isManager, isAdmin } = usersStore()
const filters = reactive({ from_date: dayjs().subtract(30, 'day').format('YYYY-MM-DD'), to_date: dayjs().format('YYYY-MM-DD'), user: '' })
const overview = createResource({ url: 'crm.ig_extensions.api.workspace.get_overview', makeParams: () => ({ ...filters }), auto: true })
const sellers = createResource({ url: 'crm.ig_extensions.api.workspace.get_sales_users', auto: true })
const maxCalls = computed(() => Math.max(1, ...(overview.data?.agents || []).map((agent) => agent.calls)))
const orderStates = [{ key: '0', label: __('Borrador'), dot: 'ig-dot-draft' }, { key: '1', label: __('Listo'), dot: 'ig-dot-ready' }, { key: '2', label: __('Cancelado'), dot: 'ig-dot-cancelled' }]
function duration(seconds) { return seconds < 60 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min` }
usePageMeta(() => ({ title: __('Reportes · International Graphics') }))
</script>
