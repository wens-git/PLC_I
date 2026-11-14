<script setup>
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Power, PowerOff, Home, RotateCcw, LocateFixed, Settings2, Pencil, ArrowLeft, ArrowRight, Play, Square, Save, Crosshair, Trash2 } from 'lucide-vue-next'
import { hmi, command, reason, run, notify, jog, saveName } from '../store'
import { number, scaled, hex, validName } from '../protocol'
import Badge from '../components/Badge.vue'
import Action from '../components/Action.vue'
import Editor from '../components/Editor.vue'
const route = useRoute(), router = useRouter()
const index = computed(() => Number(route.params.index || 0))
const axis = computed(() => hmi.state.axes.find(a => a.index === index.value) || hmi.state.axes[0])
const mode = ref('absolute'), target = ref('0.000'), speed = ref('10.000'), error = ref(''), editor = ref('')
const drafts = reactive({})
// Name edits are host metadata and must never become a position/speed draft.
const nameDrafts = reactive({})
const nameRevisions = {}
const points = computed(() => axis.value?.points || [])
const freeSlots = computed(() => (hmi.state.points || []).filter(p => p.owner == null).map(p => p.index))
const claimSlot = ref(null)
const controls = [[20, 'enable', '使能', Power], [21, 'disable', '去使能', PowerOff], [22, 'home', '回原', Home], [23, 'clear', '清故障', RotateCcw], [30, 'zero', '位置置零', LocateFixed]]
watch(index, () => { jog.stop(); Object.keys(drafts).forEach(key => delete drafts[key]); Object.keys(nameDrafts).forEach(key => delete nameDrafts[key]); error.value = ''; editor.value = '' })
watch(() => hmi.state.session, () => { Object.keys(drafts).forEach(key => delete drafts[key]); Object.keys(nameDrafts).forEach(key => delete nameDrafts[key]); target.value = '0.000'; speed.value = '10.000'; editor.value = ''; claimSlot.value = null })
onUnmounted(() => jog.stop())
function validate() {
  try { scaled(target.value); scaled(speed.value, true); error.value = ''; return true }
  catch (err) { error.value = err.message; return false }
}
async function move() {
  if (!validate()) return
  await jog.stop()
  command(mode.value === 'absolute' ? 27 : 28, 1, axis.value.index, scaled(target.value), scaled(speed.value, true))
}
async function runPoint(point) { await jog.stop(); command(29, 1, axis.value.index, point.index) }
function startJog(event, direction) {
  if (event.button !== undefined && event.button !== 0) return
  event.preventDefault()
  event.currentTarget.setPointerCapture?.(event.pointerId)
  jog.start(axis.value.index, direction)
}
function pointDraft(point, field, value) {
  if (!drafts[point.index]) drafts[point.index] = { position: point.position, speed: point.speed, epoch: hmi.state.config_epoch, session: hmi.state.session }
  drafts[point.index][field] = value
}
async function writePoint(point, teach = false) {
  try {
    const draft = drafts[point.index] || point
    const position = teach ? number(axis.value.position) : draft.position
    scaled(position); scaled(draft.speed, true)
    const success = await run(`point:${point.index}`, '/api/point', { axis: axis.value.index, point: point.index, position: Number(position), speed: Number(draft.speed), session: hmi.state.session })
    if (success) delete drafts[point.index]
  } catch (err) { notify(err.message) }
}
async function enablePoint(point, checked) {
  await run(`point:${point.index}`, '/api/config', { object_type: 3, object_index: point.index, values: { flags: (point.taught ? 2 : 0) | (checked ? 1 : 0) }, epoch: hmi.state.config_epoch, session: hmi.state.session })
}
async function renamePoint(point) {
  const draft = nameDrafts[point.index]
  if (draft == null || draft === point.name) { delete nameDrafts[point.index]; return }
  try {
    const revision = nameRevisions[point.index]
    const ok = draft.trim() ? await saveName(3, point.index, validName(draft), revision) : await saveName(3, point.index, null, revision)
    if (ok) { delete nameDrafts[point.index]; delete nameRevisions[point.index] }
  } catch (err) { notify(err.message) }
}
async function deletePoint(point) {
  // Freeing a slot is a PLC point-record commit (code 50); its host alias is removed with it.
  if (point.enabled) { notify(`P${point.index} 仍处于启用状态：请先取消启用`); return }
  if (await run(`point:${point.index}`, `/api/point/${point.index}`, { session: hmi.state.session }, { method: 'DELETE', success: `P${point.index} 已释放为空闲槽` })) { delete drafts[point.index]; delete nameDrafts[point.index] }
}
async function claimPoint() {
  if (claimSlot.value == null) return
  const slot = claimSlot.value
  const position = Number(number(axis.value.position))
  const success = await run(`point:${slot}`, '/api/point', { axis: axis.value.index, point: slot, position, speed: 60, session: hmi.state.session })
  if (success) claimSlot.value = null
}
</script>
<template>
  <div class="page">
    <div class="page-heading"><div><p class="eyebrow">手动调试</p><h1>轴与点位</h1></div><span class="muted small">{{ hmi.state.axes.length }} 个轴槽位</span></div>
    <div class="axis-tabs" role="tablist" aria-label="选择轴"><button v-for="item in hmi.state.axes" :key="item.index" role="tab" :aria-selected="axis?.index === item.index" :class="{ selected: axis?.index === item.index }" @click="router.push(`/axes/${item.index}`)"><span class="status-dot" :class="item.alarm ? 'text-danger' : item.online ? 'text-ok' : 'text-disabled'" /><span>{{ item.name }}</span><small class="mono">AX{{ item.index }}</small></button></div>
    <template v-if="axis">
      <section class="axis-readout"><div><div class="inline"><h2>{{ axis.name }}</h2><Action :icon="Pencil" title="修改轴名称" aria-label="修改轴名称" @click="editor = 'name'" /></div><div class="position-value large">{{ axis.bound ? number(axis.position) : '--' }}<span>{{ axis.unit || 'mm' }}</span></div></div><div class="readout-secondary"><span>实际速度<strong class="mono">{{ number(axis.velocity) }} <small>{{ axis.unit || 'mm' }}/s</small></strong></span><span>锁存目标<strong class="mono">{{ number(axis.target) }} <small>{{ axis.unit || 'mm' }}</small></strong></span></div><div class="badge-row"><Badge :tone="axis.online ? 'ok' : 'warn'">{{ !axis.bound ? '未绑定' : axis.online ? '在线' : '离线' }}</Badge><Badge :tone="axis.enabled ? 'ok' : 'neutral'">{{ axis.enabled ? '已使能' : '未使能' }}</Badge><Badge :tone="axis.running ? 'warn' : 'neutral'">{{ axis.running ? '运行中' : '静止' }}</Badge><Badge :tone="axis.homed ? 'ok' : 'neutral'">{{ axis.homed ? '已回原' : '未回原' }}</Badge><Badge :tone="axis.alarm ? 'danger' : 'neutral'">{{ axis.alarm ? `报警 ${axis.alarm_code}` : '无报警' }}</Badge></div><p v-for="alarm in (hmi.state.alarms || []).filter(a => a.kind === 'axis' && a.index === axis.index)" :key="alarm.code" class="error-text small" role="alert">报警 {{ alarm.code }}：{{ alarm.message }}。处理：{{ alarm.action }}</p></section>
      <div class="permit-line"><span>PLC 许可 <span class="mono">0x{{ hex(axis.permit) }}</span></span><span>{{ reason(axis.reason) }}</span><span v-if="axis.limit" class="warn-text">限位有效</span></div>
      <div class="action-row"><Action v-for="[code, action, label, icon] in controls" :key="code" :icon="icon" :pending="Boolean(hmi.pending[`command:${code}:1:${axis.index}`])" @click="command(code, 1, axis.index)">{{ label }}</Action><Action :icon="Settings2" @click="editor = 'config'">轴参数</Action></div>
      <section class="motion-layout section-block"><div class="jog-area"><header class="section-heading"><h2>点动</h2><span class="mono muted small">{{ number(axis.config?.manual_speed) }} {{ axis.unit || 'mm' }}/s</span></header><div class="jog-buttons"><button class="button jog-button" :class="{ pressed: hmi.jog?.axis === axis.index && hmi.jog.direction === -1 }" aria-label="负向点动" @pointerdown="startJog($event, -1)" @pointerup="jog.stop()" @pointercancel="jog.stop()" @lostpointercapture="jog.stop()" @contextmenu.prevent><ArrowLeft :size="24" /><span>负向</span></button><button class="button jog-button" :class="{ pressed: hmi.jog?.axis === axis.index && hmi.jog.direction === 1 }" aria-label="正向点动" @pointerdown="startJog($event, 1)" @pointerup="jog.stop()" @pointercancel="jog.stop()" @lostpointercapture="jog.stop()" @contextmenu.prevent><ArrowRight :size="24" /><span>正向</span></button></div></div>
        <form class="move-area" @submit.prevent="move"><header class="section-heading"><h2>定位</h2><div class="segmented compact"><button type="button" :class="{ selected: mode === 'absolute' }" @click="mode = 'absolute'">绝对</button><button type="button" :class="{ selected: mode === 'relative' }" @click="mode = 'relative'">相对</button></div></header><div class="move-inputs"><label>{{ mode === 'absolute' ? '目标位置' : '相对距离' }}<div class="input-unit"><input v-model="target" aria-label="目标位置" inputmode="decimal" :aria-invalid="Boolean(error)" @blur="validate" /><span>{{ axis.unit || 'mm' }}</span></div></label><label>速度<div class="input-unit"><input v-model="speed" aria-label="定位速度" inputmode="decimal" :aria-invalid="Boolean(error)" @blur="validate" /><span>{{ axis.unit || 'mm' }}/s</span></div></label><button class="button primary" type="submit" :disabled="Boolean(hmi.pending[`command:${mode === 'absolute' ? 27 : 28}:1:${axis.index}`])"><Play :size="16" />执行</button><Action :icon="Square" :pending="Boolean(hmi.pending[`command:26:1:${axis.index}`])" @click="jog.stop(); command(26, 1, axis.index)">停止</Action></div><p v-if="error" class="error-text" role="alert">{{ error }}</p></form>
      </section>
      <section class="section-block"><header class="section-heading"><h2>点位表</h2><span class="muted small">{{ points.length }} 个点位 · 空闲 {{ freeSlots.length }} 槽 · 配置纪元 <span class="mono">{{ hmi.state.config_epoch }}</span></span></header><div class="table-scroll"><table class="points-table"><thead><tr><th>槽位</th><th>状态</th><th>位置 ({{ axis.unit || 'mm' }})</th><th>速度 ({{ axis.unit || 'mm' }}/s)</th><th>启用</th><th>操作</th></tr></thead><tbody><tr v-for="(point, p) in points" :key="point.index ?? p"><td><strong class="mono">P{{ point.index ?? p }}</strong><input class="point-name" :aria-label="`P${point.index} 名称`" maxlength="32" :value="nameDrafts[point.index] ?? point.name" @focus="nameRevisions[point.index] = hmi.state.names_revision" @input="nameDrafts[point.index] = $event.target.value" @keydown.enter="renamePoint(point)" @blur="renamePoint(point)" /></td><td><Badge :tone="point.taught ? 'ok' : 'neutral'">{{ point.taught ? '已示教' : '未示教' }}</Badge></td><td><input class="table-number" :aria-label="`P${point.index} 位置`" inputmode="decimal" :value="drafts[point.index]?.position ?? number(point.position)" @input="pointDraft(point, 'position', $event.target.value)" /></td><td><input class="table-number" :aria-label="`P${point.index} 速度`" inputmode="decimal" :value="drafts[point.index]?.speed ?? number(point.speed)" @input="pointDraft(point, 'speed', $event.target.value)" /></td><td><input type="checkbox" :aria-label="`启用 P${point.index}`" :checked="Boolean(point.enabled)" :disabled="Boolean(hmi.pending[`point:${point.index}`])" @change="enablePoint(point, $event.target.checked)" /></td><td><div class="action-row nowrap"><Action :icon="Crosshair" :pending="Boolean(hmi.pending[`point:${point.index}`])" title="当前位置示教" @click="writePoint(point, true)">示教</Action><Action :icon="Save" :pending="Boolean(hmi.pending[`point:${point.index}`])" title="写入编辑点位" @click="writePoint(point)">写入</Action><Action :icon="Play" :pending="Boolean(hmi.pending[`command:29:1:${axis.index}`])" title="执行点位" @click="runPoint(point)">执行</Action><Action :icon="Trash2" :pending="Boolean(hmi.pending[`point:${point.index}`])" :disabled="point.enabled || point.index === axis.index" :title="point.index === axis.index ? 'P0 待机点不可释放' : point.enabled ? '需先取消启用' : '释放为空闲槽（清除示教记录并删除别名）'" @click="deletePoint(point)">释放</Action></div></td></tr><tr v-if="!points.length"><td colspan="6" class="empty-state">点位尚未读回</td></tr></tbody></table></div><div v-if="freeSlots.length" class="action-row"><label>认领空闲槽<select v-model="claimSlot" aria-label="选择空闲点位槽" class="table-number"><option :value="null" disabled>选择槽号</option><option v-for="slot in freeSlots" :key="slot" :value="slot">P{{ slot }}</option></select></label><Action :icon="Crosshair" :pending="claimSlot != null && Boolean(hmi.pending[`point:${claimSlot}`])" title="以当前位置示教并认领该槽" @click="claimPoint">示教并认领</Action></div></section>
      <Editor v-if="editor" :object="axis" :type="1" :kind="editor" @close="editor = ''" />
    </template>
  </div>
</template>
