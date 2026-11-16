<template>
  <Dialog v-model:open="show" :title="dialogTitle">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl :modelValue="customerName" type="text" :label="__('Cliente')" disabled />
        <FormControl v-model="deliveryDate" type="date" :label="__('Fecha de entrega')" />
        <div class="flex flex-col gap-3">
          <div
            v-for="(item, index) in items"
            :key="index"
            class="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(180px,2fr)_minmax(90px,1fr)_minmax(110px,1fr)_auto]"
          >
            <Link
              v-model="item.item_code"
              doctype="Item"
              :label="__('Producto')"
              :placeholder="__('Seleccionar producto')"
              required
            />
            <FormControl v-model="item.qty" type="number" :label="__('Cantidad')" :min="0.001" :step="0.001" />
            <FormControl
              v-model="item.rate"
              type="number"
              :label="__('Precio unitario')"
              :min="0"
              :step="0.01"
              :placeholder="__('Precio de la lista')"
            />
            <Button
              v-if="items.length > 1"
              variant="ghost"
              icon="lucide-trash-2"
              :aria-label="__('Quitar producto')"
              @click="removeItem(index)"
            />
          </div>
          <div class="flex flex-wrap gap-2">
            <Button
              variant="subtle"
              :label="__('Agregar producto')"
              iconLeft="lucide-plus"
              @click="items.push(blankItem())"
            />
          </div>
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button :label="__('Cancelar')" @click="show = false" />
        <Button
          variant="solid"
          :label="__('Guardar borrador')"
          :loading="saving"
          :disabled="loading || saving"
          @click="save"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import Link from '@/components/Controls/Link.vue'
import { call, Button, Dialog, ErrorMessage, FormControl, toast } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
  organization: { type: String, required: true },
  orderName: { type: String, default: '' },
})

const emit = defineEmits(['saved'])
const show = defineModel('open', { type: Boolean, default: false })
const items = ref([])
const customerName = ref('')
const deliveryDate = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
const modified = ref('')

const dialogTitle = computed(() => (props.orderName ? __('Editar pedido') : __('Nuevo pedido')))

function blankItem() {
  return { item_code: '', qty: 1, rate: null }
}

function todayPlus(days) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

function getErrorMessage(exception) {
  return exception?.messages?.[0] || exception?.message || __('No se pudo guardar el pedido')
}

async function load() {
  loading.value = true
  error.value = ''
  items.value = []
  customerName.value = props.organization
  deliveryDate.value = todayPlus(7)
  try {
    if (props.orderName) {
      const so = await call('frappe.client.get', { doctype: 'Sales Order', name: props.orderName })
      modified.value = so.modified
      customerName.value = so.customer_name || so.customer || props.organization
      deliveryDate.value = so.delivery_date || todayPlus(7)
      items.value = (so.items || []).map((row) => ({
        item_code: row.item_code,
        qty: row.qty,
        rate: row.rate,
      }))
    }
    if (!items.value.length) items.value = [blankItem()]
  } catch (exception) {
    error.value = getErrorMessage(exception)
    if (!items.value.length) items.value = [blankItem()]
  } finally {
    loading.value = false
  }
}

watch(
  show,
  (open) => {
    if (open) load()
  },
  { immediate: true },
)

function removeItem(index) {
  items.value.splice(index, 1)
}

async function save() {
  error.value = ''
  const lines = items.value.map((row) => ({
    item_code: row.item_code,
    qty: Number(row.qty),
    rate: row.rate === '' || row.rate == null ? null : Number(row.rate),
  }))
  if (!lines.length || lines.some((row) => !row.item_code || row.qty <= 0)) {
    error.value = __('Agrega un producto con una cantidad mayor que cero')
    return
  }
  if (lines.some((row) => row.rate != null && row.rate < 0)) {
    error.value = __('El precio no puede ser negativo')
    return
  }
  saving.value = true
  try {
    const result = props.orderName
      ? await call(
          'crm.ig_extensions.api.orders.update_sales_order_items',
          { name: props.orderName, items: lines, delivery_date: deliveryDate.value, modified: modified.value },
        )
      : await call(
          'crm.ig_extensions.api.orders.create_organization_sales_order',
          { organization: props.organization, items: lines, delivery_date: deliveryDate.value },
        )
    toast.success(__('Pedido guardado como borrador'))
    emit('saved', result?.name)
    show.value = false
  } catch (exception) {
    error.value = getErrorMessage(exception)
  } finally {
    saving.value = false
  }
}
</script>
