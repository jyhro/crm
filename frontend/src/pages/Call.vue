<template>
  <div class="flex h-full min-w-0 flex-col overflow-hidden"><LayoutHeader><template #left-header><Breadcrumbs :items="[{ label: __('Notas y llamadas'), route: { name: 'Notes' } }, { label: __('Llamada') }]" /></template></LayoutHeader><div class="flex-1 overflow-y-auto"><div v-if="call.data" class="ig-product-detail"><span class="text-sm text-ink-gray-6">{{ call.data.name }}</span><h1>{{ __('Registro de llamada') }}</h1><dl class="ig-product-facts"><div v-for="fact in facts" :key="fact.label"><dt>{{ fact.label }}</dt><dd>{{ fact.value || '—' }}</dd></div></dl><p class="mt-5 text-p-base text-ink-gray-6">{{ __('Este detalle muestra el registro del CRM. El audio y la captura automática dependen de la integración telefónica configurada.') }}</p><h2>{{ __('Notas asociadas') }}</h2><ul class="ig-ranked-list"><li v-for="note in call.data._notes || []" :key="note.name"><a :href="'/crm/notes/view/list?open=' + encodeURIComponent(note.name)">{{ note.title || note.name }}</a></li></ul><p v-if="!call.data._notes?.length" class="text-ink-gray-6">{{ __('No hay notas asociadas visibles.') }}</p><a href="/crm/call-logs/view" class="ig-inline-link mt-5">{{ __('Abrir registros en CRM') }}</a></div><div v-else class="ig-empty" role="status">{{ call.error ? (call.error.messages?.[0] || __('No tienes acceso a esta llamada.')) : __('Cargando llamada…') }}</div></div></div>
</template>
<script setup>
import LayoutHeader from '@/components/LayoutHeader.vue'
import { Breadcrumbs, createResource, usePageMeta } from 'frappe-ui'
import { computed } from 'vue'
import { formatDate } from '@/utils'
const props = defineProps({ callId: { type: String, required: true } })
const call = createResource({ url: 'crm.fcrm.doctype.crm_call_log.crm_call_log.get_call_log', params: { name: props.callId }, auto: true })
const facts = computed(() => [{ label: __('Tipo'), value: call.data.type }, { label: __('Estado técnico'), value: call.data.status }, { label: __('Desde'), value: call.data.from }, { label: __('Hasta'), value: call.data.to }, { label: __('Inicio'), value: call.data.start_time ? formatDate(call.data.start_time) : call.data.creation ? formatDate(call.data.creation) : '' }, { label: __('Duración registrada'), value: `${call.data.duration || 0} s` }, { label: __('Agente saliente'), value: call.data.caller }, { label: __('Agente receptor'), value: call.data.receiver }])
usePageMeta(() => ({ title: __('Registro de llamada') }))
</script>
