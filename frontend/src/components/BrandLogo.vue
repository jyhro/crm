<template>
  <div class="ig-brand" :class="{ 'ig-brand-official': !brand?.logo || brand.logo === fallbackLogo }">
    <img :src="brand.logo || fallbackLogo" :alt="brand.name || 'International Graphics'" />
  </div>
</template>

<script setup>
const fallbackLogo = '/assets/crm/images/international-graphics.png'
const brand = defineModel({ type: Object, default: () => ({}) })
</script>
