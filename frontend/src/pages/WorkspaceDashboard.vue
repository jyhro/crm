<template>
  <div class="ig-dashboard">
    <LayoutHeader>
      <template #left-header><Breadcrumbs :items="[{ label: __('Reportes'), route: { name: 'Dashboard' } }]" /></template>
      <template #right-header><Button :label="__('Actualizar')" iconLeft="lucide-refresh-ccw" :loading="overview.loading" @click="overview.reload()" /></template>
    </LayoutHeader>
    <main class="ig-dashboard-scroll" :aria-busy="overview.loading">
      <div class="ig-dashboard-heading"><h1>{{ __('Actividad comercial') }}</h1><p>{{ __('Llamadas y pedidos de tu equipo, según los permisos de tu cuenta.') }}</p></div>
      <form class="ig-dashboard-filters" @submit.prevent="overview.reload()">
        <label>{{ __('Desde') }}<input v-model="filters.from_date" type="date" class="form-input" required /></label>
        <label>{{ __('Hasta') }}<input v-model="filters.to_date" type="date" class="form-input" :min="filters.from_date" required /></label>
        <label v-if="isManager()">{{ __('Vendedor') }}<select v-model="filters.user" class="form-select"><option value="">{{ __('Todo el equipo autorizado') }}</option><option v-for="seller in sellers.data || []" :key="seller.value" :value="seller.value">{{ seller.label }}</option></select></label>
        <Button type="submit" variant="solid" :label="__('Ver reporte')" :loading="overview.loading" />
      </form>
      <ErrorMessage v-if="overview.error" :message="overview.error.messages?.[0] || __('No se pudo cargar el reporte. Vuelve a intentarlo.')" class="my-4" />
      <div v-if="!overview.data && overview.loading" class="ig-dashboard-empty" role="status">{{ __('Consultando la actividad registrada…') }}</div>
      <template v-if="overview.data">
        <p class="ig-dashboard-period">{{ __('Período') }}: {{ overview.data.from_date }} — {{ overview.data.to_date }}</p>
        <dl class="ig-dashboard-counts">
          <div><dt>{{ __('Llamadas registradas') }}</dt><dd>{{ number(overview.data.calls) }}</dd><p>{{ overview.data.completed }} {{ __('completadas') }} · {{ duration(overview.data.duration) }}</p></div>
          <div><dt>{{ __('Pedidos del período') }}</dt><dd>{{ number(overview.data.orders) }}</dd><p>{{ __('Creados en estas fechas') }}</p></div>
          <div><dt>{{ __('Clientes de la cartera') }}</dt><dd>{{ number(overview.data.customers) }}</dd><p>{{ __('Cartera actual visible') }}</p></div>
          <div><dt>{{ __('Productos activos') }}</dt><dd>{{ number(overview.data.catalog_products) }}</dd><p>{{ __('Catálogo actual visible') }}</p></div>
        </dl>
        <div class="ig-dashboard-columns">
          <section class="ig-dashboard-section" aria-labelledby="outcome-title">
            <div class="ig-dashboard-section-heading"><div><h2 id="outcome-title">{{ __('Resultados de llamadas') }}</h2><p>{{ __('Resultado comercial registrado por el vendedor') }}</p></div><Button :route="{ name: 'Call Logs' }" :label="__('Ver llamadas')" variant="ghost" iconRight="lucide-arrow-up-right" /></div>
            <div v-if="outcomes.length" class="ig-dashboard-outcome-content">
              <div class="ig-dashboard-donut">
                <DonutChart :data="outcomes" category="label" value="count" :palette="outcomePalette" :maxSlices="Math.max(outcomes.length, 2)" :showDataLabels="false" :centerLabel="__('Llamadas')">
                  <template #center><div class="ig-dashboard-donut-total">{{ number(overview.data.calls) }}<small>{{ __('llamadas') }}</small></div></template>
                  <template #tooltip="{ items }"><div v-for="item in items" :key="item.name" class="ig-dashboard-outcome-tooltip"><strong>{{ item.label }}</strong><span>{{ number(item.value) }} · {{ percentage(item.value) }}%</span></div></template>
                </DonutChart>
              </div>
              <ul class="ig-dashboard-outcomes" :aria-label="__('Resultados: cantidad y porcentaje de llamadas')">
                <li v-for="(outcome, index) in outcomes" :key="outcome.label">
                  <div class="ig-dashboard-row"><span class="ig-dashboard-outcome-label"><span class="ig-dashboard-outcome-dot" :style="{ backgroundColor: outcomePalette[index] }" aria-hidden="true" />{{ outcome.label }}</span><span class="ig-dashboard-values"><strong>{{ number(outcome.count) }}</strong><span>{{ percentage(outcome.count) }}%</span></span></div>
                </li>
              </ul>
            </div>
            <p v-else class="ig-dashboard-empty">{{ __('No hay llamadas en este período. Prueba otras fechas o revisa el vendedor seleccionado.') }}</p>
          </section>
          <section class="ig-dashboard-section" aria-labelledby="agents-title">
            <div class="ig-dashboard-section-heading"><div><h2 id="agents-title">{{ __('Llamadas por vendedor') }}</h2><p>{{ __('Actividad registrada en el período') }}</p></div></div>
            <ul v-if="overview.data.agents.length" class="ig-dashboard-agents"><li v-for="agent in overview.data.agents" :key="agent.user"><div><strong>{{ agent.label }}</strong><p>{{ agent.completed }} {{ __('completadas') }} · {{ duration(agent.duration) }}</p></div><span class="ig-dashboard-agent-count">{{ number(agent.calls) }}<small>{{ __('llamadas') }}</small></span></li></ul>
            <p v-else class="ig-dashboard-empty">{{ __('No hay actividad para este equipo y período.') }}</p>
          </section>
        </div>
        <section class="ig-dashboard-section ig-dashboard-orders" aria-labelledby="orders-title">
          <div class="ig-dashboard-section-heading"><div><h2 id="orders-title">{{ __('Pedidos') }}</h2><p>{{ __('Evolución y estado durante el período') }}</p></div><Button :route="{ name: 'Sales Orders' }" :label="__('Ver pedidos')" variant="ghost" iconRight="lucide-arrow-up-right" /></div>
          <template v-if="overview.data.orders">
            <div class="ig-dashboard-order-content"><div class="ig-dashboard-chart"><LineChart :showDataPoints="true" :echartOptions="{ yAxis: { minInterval: 1 } }" :data="overview.data.trend" x="transaction_date" :y="['count']" :seriesConfig="{ count: { label: __('Pedidos'), color: '#ed1b24' } }" :xAxis="{ type: 'time', timeGrain: 'day' }" /></div><dl class="ig-dashboard-states"><div v-for="state in orderStates" :key="state.key"><dt><span class="ig-dot" :class="state.dot" />{{ state.label }}</dt><dd>{{ number(overview.data.states[state.key] || 0) }}</dd></div></dl></div>
            <h3 v-if="overview.data.products.length">{{ __('Productos solicitados') }}</h3><ul class="ig-ranked-list"><li v-for="item in overview.data.products" :key="item.item_code + item.uom"><router-link :to="{ name: 'Product', params: { productId: item.item_code } }">{{ item.item_name || item.item_code }}</router-link><strong>{{ number(item.qty) }} <small>{{ item.uom }}</small></strong></li></ul>
          </template>
          <div v-else class="ig-dashboard-order-empty"><span class="lucide-shopping-cart" aria-hidden="true" /><div><h3>{{ __('Todavía no hay pedidos en este período') }}</h3><p>{{ __('Consulta otros días o abre Pedidos para comenzar.') }}</p></div></div>
        </section>
        <footer class="ig-dashboard-footer"><details><summary>{{ __('Cómo se calcula este reporte') }}</summary><p>{{ __('Las fechas filtran llamadas y pedidos. La cartera y el catálogo muestran su estado actual. Solo se incluyen registros visibles para tu cuenta.') }}</p><p>{{ __('Los resultados comerciales son independientes del estado técnico de la llamada. Sin resultado registrado no significa llamada fallida. El estado «completada» no confirma una conversación humana; el audio depende del proveedor telefónico.') }}</p><p>{{ __('Un pedido «Listo» está validado en ERPNext; no confirma su envío a Profit.') }}</p></details><Button v-if="isAdmin()" :route="{ name: 'Dashboard Advanced' }" :label="__('Gráficos avanzados')" variant="ghost" /></footer>
      </template>
    </main>
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
// Match the native donut's descending slice order so the single accessible
// legend, ring and tooltip always use the same category colors.
const outcomes = computed(() => [...(overview.data?.outcomes || [])].sort((a, b) => b.count - a.count))
const outcomePalette = computed(() => outcomes.value.map((outcome, index) => {
  const label = outcome.label.toLocaleLowerCase('es')
  if (label === 'sin resultado comercial registrado') return '#8b8d94'
  if (/no interesad|rechazad/.test(label)) return '#d65a64'
  if (/no contesta|ocupad|volver a llamar/.test(label)) return '#c89435'
  if (/interesad|venta|exitos/.test(label)) return '#3b9d7a'
  return ['#648dca', '#a783c5', '#cf805a', '#48a2aa'][index % 4]
}))
const orderStates = [{ key: '0', label: __('Borrador'), dot: 'ig-dot-draft' }, { key: '1', label: __('Listo'), dot: 'ig-dot-ready' }, { key: '2', label: __('Cancelado'), dot: 'ig-dot-cancelled' }]
const number = (value) => new Intl.NumberFormat('es').format(value || 0)
function percentage(count) { return number(Math.round(count / Math.max(overview.data.calls, 1) * 1000) / 10) }
function duration(seconds) { return seconds < 60 ? `${Math.round(seconds)} s` : `${Math.round(seconds / 60)} min` }
usePageMeta(() => ({ title: __('Reportes · International Graphics') }))
</script>
<style scoped>
.ig-dashboard{flex:1;min-height:0;min-width:0;display:flex;flex-direction:column;overflow:hidden;color:var(--ink-gray-9)}
.ig-dashboard-scroll{flex:1;min-height:0;overflow-y:auto;padding:28px;scrollbar-color:var(--outline-gray-3) transparent}
.ig-dashboard-heading h1{font-size:24px;line-height:1.3;font-weight:650;letter-spacing:-.025em}
.ig-dashboard-heading p,.ig-dashboard-section-heading p{margin-top:6px;color:var(--ink-gray-6);font-size:13px;line-height:1.5}
.ig-dashboard-filters{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-top:24px}
.ig-dashboard-filters label{display:flex;flex-direction:column;gap:7px;flex:1;max-width:260px;min-width:140px;font-size:12px;color:var(--ink-gray-7)}
.ig-dashboard-filters input,.ig-dashboard-filters select{width:100%;min-height:36px}
.ig-dashboard-period{font-size:12px;color:var(--ink-gray-6);margin-top:24px}
.ig-dashboard-counts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px;padding:20px 0 24px;margin-bottom:24px;border-bottom:1px solid var(--outline-gray-2)}
.ig-dashboard-counts dt{font-size:13px;color:var(--ink-gray-7);line-height:1.4}
.ig-dashboard-counts dd{font-size:30px;font-weight:600;line-height:1.2;margin-top:10px;font-variant-numeric:tabular-nums;letter-spacing:-.025em}
.ig-dashboard-counts p{font-size:12px;color:var(--ink-gray-6);margin-top:6px;line-height:1.5}
.ig-dashboard-columns{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:24px}
.ig-dashboard-section{min-width:0;border:1px solid var(--outline-gray-2);border-radius:12px;padding:20px}
.ig-dashboard-section-heading{display:flex;align-items:start;justify-content:space-between;gap:12px}
.ig-dashboard-section h2{font-size:16px;font-weight:600;line-height:1.4}
.ig-dashboard-outcome-content{display:flex;align-items:center;gap:24px;margin-top:20px}
.ig-dashboard-donut{height:180px;width:180px;flex-shrink:0}
/* The native chart supplies keyboard/tooltip support. Its built-in toggle
   legend is replaced by the single, fully labeled data list beside the ring. */
.ig-dashboard-donut :deep([data-slot="chart-legend"]){display:none}
.ig-dashboard-donut-total{text-align:center;font-size:26px;font-weight:600;line-height:1.2;font-variant-numeric:tabular-nums;color:var(--ink-gray-9)}
.ig-dashboard-donut-total small{display:block;font-size:12px;font-weight:400;color:var(--ink-gray-7);margin-top:5px}
.ig-dashboard-outcomes{display:grid;gap:18px;flex:1;min-width:0}
.ig-dashboard-outcome-label{display:flex;align-items:baseline;gap:8px;min-width:0;overflow-wrap:anywhere}
.ig-dashboard-outcome-dot{width:8px;height:8px;flex-shrink:0;display:inline-block;border-radius:50%;align-self:center}
.ig-dashboard-outcome-tooltip{display:grid;gap:6px;max-width:240px;font-size:13px;line-height:1.5;color:var(--ink-gray-9)}
.ig-dashboard-outcome-tooltip span{color:var(--ink-gray-7);font-variant-numeric:tabular-nums}
.ig-dashboard-row{display:flex;align-items:baseline;justify-content:space-between;gap:20px;font-size:13px;line-height:1.5}
.ig-dashboard-values{display:flex;gap:12px;flex-shrink:0;font-variant-numeric:tabular-nums}
.ig-dashboard-values>span{color:var(--ink-gray-6);min-width:40px;text-align:right}
.ig-dashboard-agents{margin-top:16px}
.ig-dashboard-agents li{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:14px 0;border-bottom:1px solid var(--outline-gray-2);font-size:13px}
.ig-dashboard-agents li:last-child{border:0;padding-bottom:0}
.ig-dashboard-agents strong{font-weight:500}
.ig-dashboard-agents p{margin-top:6px;color:var(--ink-gray-6);font-size:12px}
.ig-dashboard-agent-count{text-align:right;font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
.ig-dashboard-agent-count small{display:block;font-weight:400;font-size:12px;color:var(--ink-gray-6);margin-top:4px}
.ig-dashboard-orders{margin-top:24px}
.ig-dashboard-order-empty{display:flex;align-items:center;gap:16px;padding:26px 0 4px}
.ig-dashboard-order-empty>span{font-size:24px;color:var(--ink-gray-5)}
.ig-dashboard h3{font-size:14px;font-weight:500;line-height:1.5}
.ig-dashboard-order-empty p,.ig-dashboard-empty{font-size:13px;line-height:1.6;color:var(--ink-gray-6)}
.ig-dashboard-order-empty p{margin-top:4px}
.ig-dashboard-empty{padding:28px 0 8px;max-width:60ch}
.ig-dashboard-order-content{display:grid;grid-template-columns:minmax(0,1fr) 180px;gap:24px;margin:24px 0}
.ig-dashboard-chart{height:240px;min-width:0}
.ig-dashboard-states{display:grid;align-content:center;gap:20px}
.ig-dashboard-states>div{display:flex;justify-content:space-between;font-size:13px;gap:12px}
.ig-dashboard-states dd{font-weight:600;font-variant-numeric:tabular-nums}
.ig-dashboard-footer{display:flex;justify-content:space-between;align-items:start;gap:20px;margin-top:20px;color:var(--ink-gray-6);font-size:12px;line-height:1.6}
.ig-dashboard-footer details{max-width:75ch}
.ig-dashboard-footer summary{cursor:pointer;padding:6px 0;color:var(--ink-gray-7)}
.ig-dashboard-footer p{margin-top:8px}
@media(min-width:1001px) and (max-width:1350px){.ig-dashboard-outcome-content{flex-direction:column;gap:16px}.ig-dashboard-outcomes{width:100%}}
@media(max-width:1000px){.ig-dashboard-columns{grid-template-columns:1fr}.ig-dashboard-filters label{max-width:none}}
@media(max-width:639px){.ig-dashboard-outcome-content{flex-direction:column;gap:16px}.ig-dashboard-outcomes{width:100%}.ig-dashboard-donut{width:180px;height:180px}.ig-dashboard-scroll{padding:20px 16px}.ig-dashboard-heading h1{font-size:22px}.ig-dashboard-filters{gap:12px}.ig-dashboard-filters label{min-width:calc(50% - 12px)}.ig-dashboard-filters label:last-of-type{flex-basis:100%}.ig-dashboard-counts{grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 16px}.ig-dashboard-section{padding:16px}.ig-dashboard-section-heading{flex-wrap:wrap}.ig-dashboard-columns{gap:16px}.ig-dashboard-orders{margin-top:16px}.ig-dashboard-order-content{grid-template-columns:1fr}.ig-dashboard-footer{flex-direction:column;gap:8px}.ig-dashboard-row{gap:12px}.ig-dashboard-counts dd{font-size:28px}}
</style>
