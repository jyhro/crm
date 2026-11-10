<template>
  <Dialog v-model:open="show" :title="dialogTitle">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          :modelValue="customerName"
          type="text"
          :label="__('Customer')"
          disabled
        />
        <div class="flex flex-col gap-3">
          <div
            v-for="(item, index) in items"
            :key="index"
            class="grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(180px,2fr)_minmax(90px,1fr)_minmax(110px,1fr)_auto]"
          >
            <Link
              v-model="item.item_code"
              doctype="Item"
              :label="__('Product')"
              :placeholder="__('Select a product')"
              required
            />
            <FormControl
              v-model="item.qty"
              type="number"
              :label="__('Qty')"
              :min="0.001"
              :step="0.001"
            />
            <FormControl
              v-model="item.rate"
              type="number"
              :label="__('Rate')"
              :min="0"
              :step="0.01"
              :placeholder="__('Standard price')"
            />
            <Button
              v-if="items.length > 1"
              variant="ghost"
              icon="lucide-trash-2"
              :aria-label="__('Remove item')"
              @click="removeItem(index)"
            />
          </div>
          <div class="flex flex-wrap gap-2">
            <Button
              variant="subtle"
              :label="__('Add product')"
              iconLeft="lucide-plus"
              @click="items.push(blankItem())"
            />
            <Button
              variant="subtle"
              :label="__('Add products from deal')"
              iconLeft="lucide-download"
              :loading="prefilling"
              @click="addDealProducts"
            />
          </div>
        </div>
        <ErrorMessage :message="error" />
      </div>
    </template>
    <template #actions>
      <div class="flex justify-end gap-2">
        <Button :label="__('Cancel')" @click="show = false" />
        <Button
          variant="solid"
          :label="__('Save draft')"
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
  deal: { type: String, required: true },
  dealDoc: { type: Object, default: () => ({}) },
  quotationName: { type: String, default: '' },
})

const emit = defineEmits(['saved'])
const show = defineModel('open', { type: Boolean, default: false })
const items = ref([])
const customerName = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
const prefilling = ref(false)

const dialogTitle = computed(() =>
  props.quotationName ? __('Edit Quotation') : __('New Quotation'),
)

function blankItem() {
  return { item_code: '', qty: 1, rate: null }
}

function getErrorMessage(exception) {
  return exception?.messages?.[0] || exception?.message || __('Could not save quotation')
}

async function load() {
  loading.value = true
  error.value = ''
  items.value = []

  try {
    if (props.quotationName) {
      const quotation = await call('frappe.client.get', {
        doctype: 'Quotation',
        name: props.quotationName,
      })
      customerName.value = quotation.customer_name || quotation.party_name || ''
      items.value = (quotation.items || []).map((row) => ({
        item_code: row.item_code,
        qty: row.qty,
        rate: row.rate,
      }))
    } else {
      customerName.value =
        props.dealDoc.organization || props.dealDoc.lead_name || props.deal
      const prefilled = await call(
        'crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.prefill_quotation_items',
        { crm_deal: props.deal },
      )
      items.value = (prefilled || []).map((row) => ({
        item_code: row.item_code,
        qty: row.qty || 1,
        rate: row.price_list_rate > 0 ? row.price_list_rate : null,
      }))
    }
    if (!items.value.length) items.value = [blankItem()]
  } catch (exception) {
    error.value = getErrorMessage(exception)
    if (!props.quotationName && !items.value.length) items.value = [blankItem()]
  } finally {
    loading.value = false
  }
}

watch(show, (open) => {
  if (open) load()
})

function removeItem(index) {
  items.value.splice(index, 1)
}

async function addDealProducts() {
  prefilling.value = true
  error.value = ''
  try {
    const prefilled = await call(
      'crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.prefill_quotation_items',
      { crm_deal: props.deal },
    )
    items.value = (prefilled || []).map((row) => ({
      item_code: row.item_code,
      qty: row.qty || 1,
      rate: row.price_list_rate > 0 ? row.price_list_rate : null,
    }))
    if (!items.value.length) items.value = [blankItem()]
  } catch (exception) {
    error.value = getErrorMessage(exception)
  } finally {
    prefilling.value = false
  }
}

async function save() {
  error.value = ''
  const lines = items.value.map((row) => ({
    item_code: row.item_code,
    qty: Number(row.qty),
    rate: row.rate === '' || row.rate == null ? null : Number(row.rate),
  }))

  if (!lines.length || lines.some((row) => !row.item_code || row.qty <= 0)) {
    error.value = __('Add a product and a quantity greater than zero')
    return
  }
  if (lines.some((row) => row.rate != null && row.rate < 0)) {
    error.value = __('Rate cannot be negative')
    return
  }

  saving.value = true
  try {
    const result = props.quotationName
      ? await call(
          'crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.update_quotation_items',
          { name: props.quotationName, items: lines },
        )
      : await call(
          'crm.fcrm.doctype.erpnext_crm_settings.erpnext_crm_settings.create_quotation',
          { crm_deal: props.deal, items: lines },
        )
    toast.success(__('Quotation saved as draft'))
    emit('saved', result.name)
    show.value = false
  } catch (exception) {
    error.value = getErrorMessage(exception)
  } finally {
    saving.value = false
  }
}
</script>
