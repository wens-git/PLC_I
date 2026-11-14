<script setup>
import { computed, ref } from 'vue'
import { Eye, Search } from 'lucide-vue-next'
import { hmi } from '../store'
import Badge from '../components/Badge.vue'
const onlyOn = ref(false), search = ref('')
const groups = computed(() => ['x','y'].map(type => ({ type, values: (hmi.state.io?.[type] || []).map((value,index) => ({value,index})).filter(item => (!onlyOn.value || item.value) && `${type.toUpperCase()}${item.index}`.includes(search.value.toUpperCase())), total: hmi.state.io?.[type]?.length || 0 })))
</script>
<template>
  <div class="page"><div class="page-heading"><div><p class="eyebrow">数字信号</p><h1>I/O 监视</h1></div><Badge><Eye :size="14" />只读</Badge></div><div class="filter-bar"><label class="check-field"><input v-model="onlyOn" type="checkbox" />仅显示有效信号</label><label class="search-field"><Search :size="16" /><input v-model="search" placeholder="搜索 X0 / Y0" aria-label="搜索 I/O" /></label></div>
    <section v-for="group in groups" :key="group.type" class="section-block"><header class="section-heading"><h2>{{ group.type === 'x' ? 'X 输入' : 'Y 输出' }}</h2><span class="mono muted small">{{ group.total }} 点</span></header><div class="io-grid"><div v-for="item in group.values" :key="item.index" class="io-cell" :class="{ on: item.value }" :aria-label="`${group.type.toUpperCase()}${item.index}: ${item.value ? '1 有效' : '0 无效'}`"><span class="status-dot" /><strong class="mono">{{ group.type.toUpperCase() }}{{ item.index }}</strong><span class="mono">{{ item.value ? '1' : '0' }}</span></div></div><p v-if="!group.values.length" class="empty-state">没有符合条件的信号</p></section>
  </div>
</template>
