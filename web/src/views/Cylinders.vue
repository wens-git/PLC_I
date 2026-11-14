<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Search, ArrowRight, Home, Square, Settings2, Pencil } from 'lucide-vue-next'
import { hmi, command, reason } from '../store'
import { hex } from '../protocol'
import { cylinderSide, cylinderStatus, cylinderType } from '../cylinder'
import Badge from '../components/Badge.vue'
import Action from '../components/Action.vue'
import Editor from '../components/Editor.vue'
const route = useRoute()
const filter = ref(route.params.index === undefined ? 'bound' : 'all'), search = ref(''), editor = ref(null)
const rows = computed(() => hmi.state.cylinders.filter(c => (filter.value === 'all' || filter.value === 'bound' && c.bound || filter.value === 'online' && c.online || filter.value === 'alarm' && c.alarm) && `${c.name} CY${String(c.index).padStart(2, '0')} ${c.index}`.includes(search.value)))

</script>
<template>
  <div class="page"><div class="page-heading"><div><p class="eyebrow">执行器监控</p><h1>气缸</h1></div><Badge>{{ rows.length }} / {{ hmi.state.cylinders.length }} 对象</Badge></div>
    <div class="filter-bar"><div class="segmented"><button v-for="[key, label] in [['bound','已绑定'],['online','在线'],['alarm','报警'],['all','全部']]" :key="key" :class="{ selected: filter === key }" @click="filter = key">{{ label }}</button></div><label class="search-field"><Search :size="16" /><input v-model="search" placeholder="搜索名称或编号" aria-label="搜索气缸" /></label></div>
    <div class="table-scroll"><table class="cylinder-table"><thead><tr><th>对象</th><th>连接</th><th>端位</th><th>PLC 许可 / 原因</th><th>动作</th><th>配置</th></tr></thead><tbody><tr v-for="c in rows" :key="c.index" :class="{ 'selected-row': String(c.index) === route.params.index }"><td><span class="mono muted object-id">CY{{ String(c.index).padStart(2,'0') }}</span><strong>{{ c.name }}</strong><small class="block muted">{{ cylinderType(c.config) }}</small></td><td><Badge :tone="!c.bound ? 'neutral' : c.alarm ? 'danger' : c.online ? 'ok' : 'warn'">{{ !c.bound ? '未绑定' : c.alarm ? '报警' : c.online ? '在线' : '离线' }}</Badge></td><td><Badge :tone="c.alarm ? 'danger' : c.moving ? 'warn' : c.home || c.move ? 'ok' : 'neutral'">{{ cylinderStatus(c) }}</Badge><small v-for="side in ['move', 'home']" :key="side" class="block muted">{{ cylinderSide(c.config, side).label }}：{{ cylinderSide(c.config, side).input }} · {{ cylinderSide(c.config, side).confirmation }}</small></td><td><span class="mono small">0x{{ hex(c.permit) }}</span><small class="block muted">{{ reason(c.reason) }}</small></td><td><div class="action-row nowrap"><Action :icon="ArrowRight" :pending="Boolean(hmi.pending[`command:40:2:${c.index}`])" @click="command(40,2,c.index)">{{ cylinderSide(c.config, 'move').label }}</Action><Action :icon="Home" :pending="Boolean(hmi.pending[`command:41:2:${c.index}`])" @click="command(41,2,c.index)">{{ cylinderSide(c.config, 'home').label }}</Action><Action :icon="Square" title="取消本次请求并撤销两路输出；不代表机械立即停止或安全急停" :pending="Boolean(hmi.pending[`command:42:2:${c.index}`])" @click="command(42,2,c.index)">取消</Action></div></td><td><div class="inline"><Action :icon="Settings2" title="气缸参数" :aria-label="`${c.name} 参数`" @click="editor = { object: c, kind: 'config' }" /><Action :icon="Pencil" title="修改名称" :aria-label="`${c.name} 修改名称`" @click="editor = { object: c, kind: 'name' }" /></div></td></tr><tr v-if="!rows.length"><td colspan="6" class="empty-state">没有符合条件的气缸</td></tr></tbody></table></div>
    <Editor v-if="editor" :object="editor.object" :type="2" :kind="editor.kind" @close="editor = null" />
  </div>
</template>
