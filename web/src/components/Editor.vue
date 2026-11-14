<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { cylinderSide, cylinderType, cylinderValues } from '../cylinder'
import { Save, X } from 'lucide-vue-next'
import { hmi, run, notify, saveName } from '../store'
import { NAME_MAX, scaled, validName } from '../protocol'
import Action from './Action.vue'

const props = defineProps({ object: Object, type: Number, kind: String })
const emit = defineEmits(['close'])
const form = reactive({})
const error = ref('')
const epoch = ref(hmi.state.config_epoch)
const namesRevision = hmi.state.names_revision
const session = ref(hmi.state.session)
const axisFields = [
  ['positive_limit', '软正限位', 'mm'], ['negative_limit', '软负限位', 'mm'],
  ['manual_speed', '手动速度', 'mm/s'], ['auto_speed', '自动速度', 'mm/s'],
  ['acceleration', '加速度', 'mm/s²'], ['deceleration', '减速度', 'mm/s²'], ['estop_deceleration', '急停减速度', 'mm/s²'],
]
const cylinderFields = computed(() => [
  ['delay_ms', `${cylinderSide(props.object.config, 'move').label}确认延时`, 'ms'],
  ['home_delay_ms', `${cylinderSide(props.object.config, 'home').label}确认延时`, 'ms'],
  ['timeout_ms', '动作总超时', 'ms'],
])
// 轴参数初始值：空/未设置/占位最小值（0.001）时给现场一组可用默认值。
const MOTION_DEFAULTS = { manual_speed: 5, auto_speed: 5, acceleration: 2000, deceleration: 2000, estop_deceleration: 2000 }
Object.assign(form, props.object?.config ? JSON.parse(JSON.stringify(props.object.config)) : {}, { name: props.object?.name || '' })
if (props.type === 1) {
  for (const [field] of axisFields) {
    if (field.endsWith('_limit')) continue
    const value = Number(form[field])
    if (!Number.isFinite(value) || value <= 0.001) form[field] = MOTION_DEFAULTS[field]
  }
}
watch(() => hmi.state.session, () => emit('close'))
async function save() {
  error.value = ''
  try {
    if (props.kind === 'name') {
      // Names never touch the PLC, so a changed config epoch does not block them.
      if (await saveName(props.type, props.object.index, validName(form.name), namesRevision)) emit('close')
      return
    }
    if (hmi.state.config_epoch !== epoch.value) throw new Error('配置纪元已变化，请关闭后重开再提交')
    let values = {}
    if (props.type === 1) {
      for (const [field, label] of axisFields) {
        const text = String(form[field] ?? '').trim()
        if (text === '' || Number.isNaN(Number(text))) {
          throw new Error(`${label}不能为空：手动/自动速度填 5 mm/s，加速度/减速度/急停减速度填 2000 mm/s²`)
        }
        if (!field.endsWith('_limit') && !(Number(text) > 0)) {
          throw new Error(`${label}必须大于 0：手动/自动速度填 5 mm/s，加速度/减速度/急停减速度填 2000 mm/s²`)
        }
        scaled(form[field], !field.endsWith('_limit'))
        values[field] = Number(form[field])
      }
      values.flags = Number(form.flags) & 1
      if (values.negative_limit >= values.positive_limit) throw new Error('软负限位必须小于软正限位')
    } else {
      values = cylinderValues(form, props.object.config)
    }
    const payload = { object_type: props.type, object_index: props.object.index, epoch: epoch.value, session: session.value, values }
    if (await run('editor', '/api/config', payload)) emit('close')
  } catch (err) { error.value = err.message; notify(err.message) }
}
</script>
<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <section role="dialog" aria-modal="true" :aria-label="kind === 'name' ? '修改名称' : '对象参数'" class="modal" @keydown.esc="emit('close')">
      <header class="section-heading"><h2>{{ object.name }} · {{ kind === 'name' ? '修改名称' : '对象参数' }}</h2><Action :icon="X" title="关闭" aria-label="关闭" @click="emit('close')" /></header>
      <form novalidate @submit.prevent="save">
        <label v-if="kind === 'name'">名称<input v-model="form.name" autofocus :maxlength="NAME_MAX" required /><span class="muted small">名称只保存在上位机，不写入 PLC</span></label>
        <div v-else class="form-grid">
          <label v-for="[field, label, unit] in (type === 1 ? axisFields : cylinderFields)" :key="field">{{ label }}<div class="input-unit"><input v-model="form[field]" required inputmode="decimal" :aria-label="label" /><span>{{ unit }}</span></div></label>
          <label v-if="type === 1" class="check-field"><input type="checkbox" :checked="Number(form.flags) & 1" @change="form.flags = $event.target.checked ? 1 : 0" />软限位启用</label>
          <template v-if="type === 2">
            <p class="muted small">工程配置（只读）：{{ cylinderType(object.config) }} · wiring_flags {{ object.config?.wiring_flags ?? '--' }}</p>
            <p v-for="side in ['move', 'home']" :key="side" class="muted small">{{ cylinderSide(object.config, side).label }}：{{ cylinderSide(object.config, side).input }} · {{ cylinderSide(object.config, side).confirmation }}；输出 {{ object.config?.[`${side}_y`] === 65535 ? '未映射' : object.config?.[`${side}_y`] === undefined ? '配置未读回' : `Y${object.config[`${side}_y`]}` }}</p>
            <p class="muted small">有传感器时须持续有效达到确认延时；无传感器时按本次请求计时完成。两侧延时均须小于动作总超时，无传感器侧延时须大于 0。</p>
          </template>
        </div>
        <p v-if="kind !== 'name' && !object.config" class="error-text">配置尚未完整读回，无法提交。</p>
        <p v-if="error" role="alert" class="error-text">{{ error }}</p>
        <p v-if="kind !== 'name'" class="muted small">配置纪元 <span class="mono">{{ epoch }}</span></p>
        <footer class="modal-footer"><Action @click="emit('close')">取消</Action><Action v-if="kind === 'name'" @click="saveName(type, object.index, null).then(ok => ok && emit('close'))">恢复默认</Action><button class="button primary" type="submit" :disabled="hmi.pending.editor || (kind !== 'name' && !object.config)"><Save :size="16" />{{ kind === 'name' ? '保存名称' : hmi.pending.editor ? '提交中' : '提交并读回' }}</button></footer>
      </form>
    </section>
  </div>
</template>
