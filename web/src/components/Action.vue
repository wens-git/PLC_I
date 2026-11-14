<script setup>
import { LoaderCircle } from 'lucide-vue-next'
defineProps({ icon: [Object, Function], pending: Boolean, disabled: Boolean, primary: Boolean, danger: Boolean, title: String })
</script>
<template>
  <button type="button" class="button" :class="{ primary, danger }" :disabled="disabled || pending" :title="title" :aria-busy="pending">
    <LoaderCircle v-if="pending" class="spin" :size="16" /><component :is="icon" v-else-if="icon" :size="16" /><slot />
  </button>
</template>
