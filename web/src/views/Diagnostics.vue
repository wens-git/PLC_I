<script setup>
import { computed, ref } from 'vue'
import { hmi } from '../store'
import { hex } from '../protocol'
import Badge from '../components/Badge.vue'
const filter = ref('all')
const filters = [['all', '全部'], ['command', '命令'], ['alarm', '报警'], ['link', '通信'], ['rejected', '拒绝 / 异常']]
const failed = e => e.good === false || e.level === 'error' || Number(e.result ?? 0) > 0
const events = computed(() => [...(hmi.state.events || []), ...hmi.history]
  .sort((a, b) => new Date(b.time || b.timestamp || 0) - new Date(a.time || a.timestamp || 0))
  .filter(e => filter.value === 'all' || (filter.value === 'rejected' ? failed(e) : e.category === filter.value))
  .slice(0, 200))
// The backend resolves each alarm code to a concrete cause and remedy from the protocol catalogue.
const alarms = computed(() => (hmi.state.alarms || []).map(alarm => {
  const collection = alarm.kind === 'axis' ? hmi.state.axes : hmi.state.cylinders
  const item = collection?.find(o => o.index === alarm.index)
  return { ...alarm, label: `${alarm.kind === 'axis' ? '轴' : '气缸'} ${alarm.index}${item?.name ? ` · ${item.name}` : ''}` }
}))
const raw = computed(() => {
  const words = hmi.state.raw_words || hmi.state.raw || {}
  return Array.isArray(words) ? [['快照', words]] : Object.entries(words).filter(([, value]) => Array.isArray(value))
})
function time(value) { if (!value) return '--'; if (typeof value === 'number' && value < 1e12) value *= 1000; const d = new Date(value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleTimeString('zh-CN', { hour12: false }) }
function outcome(e) {
  if (e.category === 'alarm') return e.level === 'ok' ? ['ok', '报警解除'] : ['danger', `报警 ${e.alarm}`]
  if (Number(e.result || 0) > 0) return ['danger', `拒绝 ${e.result}`]
  if (failed(e)) return ['danger', '异常']
  return ['ok', e.category === 'command' ? '已受理' : e.category === 'link' ? '通信' : '已记录']
}
</script>
<template>
  <div class="page"><div class="page-heading"><div><p class="eyebrow">状态与追溯</p><h1>诊断</h1></div><Badge :tone="alarms.length ? 'danger' : 'ok'">{{ alarms.length }} 个当前报警</Badge></div>
    <p v-if="hmi.state.names_error" class="error-text" role="alert">{{ hmi.state.names_error }}</p>
    <p v-if="hmi.state.names_stale" class="warn-text" role="alert">PLC 绑定纪元已变化，名称可能对应旧硬件，请逐项核对。</p>
    <section class="section-block"><header class="section-heading"><h2>当前报警</h2><span class="muted small">累计上升沿 {{ hmi.state.alarm_count || 0 }}</span></header>
      <div class="table-scroll"><table><thead><tr><th>报警码</th><th>对象</th><th>具体问题</th><th>处理方法</th></tr></thead><tbody>
        <tr v-for="item in alarms" :key="`${item.object}:${item.code}`"><td class="mono error-text">{{ item.code }}</td><td>{{ item.label }}</td><td>{{ item.message }}<small v-if="item.drive_error" class="block muted mono">驱动错误码 0x{{ hex(item.drive_error, 8) }}</small></td><td>{{ item.action }}</td></tr>
        <tr v-if="!alarms.length"><td colspan="4" class="empty-state">当前无对象报警</td></tr>
      </tbody></table></div></section>
    <section class="section-block"><header class="section-heading"><h2>事件与命令历史</h2><div class="segmented compact"><button v-for="[key, label] in filters" :key="key" :class="{ selected: filter === key }" @click="filter = key">{{ label }}</button></div></header>
      <div class="table-scroll history-table"><table><thead><tr><th>时间</th><th>结果</th><th>事件</th><th>处理建议</th><th>序号 / 来源</th></tr></thead><tbody>
        <tr v-for="(event, i) in events" :key="i"><td class="mono nowrap">{{ time(event.time || event.timestamp) }}</td><td><Badge :tone="outcome(event)[0]">{{ outcome(event)[1] }}</Badge></td><td>{{ event.message || event.detail || JSON.stringify(event) }}<small v-if="event.message && event.detail && event.detail !== event.message && !event.message.includes(event.detail)" class="block muted">{{ event.detail }}</small></td><td class="small">{{ event.action || '--' }}</td><td class="mono small">{{ event.seq || '--' }} / {{ event.source || 'PLC' }}</td></tr>
        <tr v-if="!events.length"><td colspan="5" class="empty-state">暂无事件</td></tr>
      </tbody></table></div></section>
    <section class="section-block"><header class="section-heading"><h2>原始寄存器</h2><span class="muted small">只读 · HEX WORD</span></header><details v-for="[name, words] in raw" :key="name" class="raw-block"><summary>{{ name }} <span class="mono muted">{{ words.length }} W</span></summary><div class="raw-grid"><div v-for="(word, i) in words" :key="i"><span class="muted">+{{ String(i).padStart(3, '0') }}</span><strong>{{ hex(word) }}</strong></div></div></details><p v-if="!raw.length" class="empty-state">后端尚未发布原始字快照</p></section>
  </div>
</template>
