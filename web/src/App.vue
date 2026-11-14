<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Wrench, LayoutDashboard, MoveHorizontal, Cylinder, CircuitBoard, Activity, OctagonX, RotateCcw, Play, Pause, Unlock, Plug, Unplug, Settings2, X, WifiOff, Check, AlertTriangle } from 'lucide-vue-next'
import { hmi, ready, start, shutdown, run, command, jog } from './store'
import { machineState, autoConditions } from './system'
import Badge from './components/Badge.vue'
import Action from './components/Action.vue'
const route = useRoute()
const settings = ref(false)
const mode = ref('mock'), host = ref('192.168.6.6'), port = ref(1502), unit = ref(1)
const clock = ref(new Date().toLocaleTimeString('zh-CN', { hour12: false }))
const machine = computed(() => machineState(hmi.state))
const conds = computed(() => autoConditions(hmi.state))
const links = [{ path: '/', name: '总览', icon: LayoutDashboard }, { path: '/axes', name: '轴与点位', icon: MoveHorizontal }, { path: '/cylinders', name: '气缸', icon: Cylinder }, { path: '/io', name: 'I/O', icon: CircuitBoard }, { path: '/diagnostics', name: '诊断', icon: Activity }]
const disconnectedTitle = computed(() => hmi.state.connected ? '握手或状态流不可用' : '设备未连接')
const systemCommand = async code => { await jog.stop(); command(code) }
const sysPending = (...codes) => codes.some(code => Boolean(hmi.pending[`command:${code}:0:0`]))
let clockTimer
onMounted(() => { start(); clockTimer = setInterval(() => { clock.value = new Date().toLocaleTimeString('zh-CN', { hour12: false }) }, 1000) })
onUnmounted(() => { shutdown(); clearInterval(clockTimer) })
async function connect() {
  await jog.stop()
  if (await run('connect', '/api/connect', { mode: mode.value, host: host.value, port: Number(port.value), unit: Number(unit.value) })) settings.value = false
}
async function disconnect() { await jog.stop(); await run('connect', '/api/disconnect', {}); settings.value = false }
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink to="/" class="brand"><Wrench :size="24" /><span>李佳树的创意工坊<small>设备控制台 · XJV1</small></span></RouterLink>
      <div class="system-controls" aria-label="整机控制">
        <Action :icon="RotateCcw" :pending="sysPending(1)" :class="{ active: hmi.state.resetting }" title="全局复位（与现场物理复位二选一）" @click="systemCommand(1)">{{ hmi.state.resetting ? '复位中' : '复位' }}</Action>
        <Action :icon="Play" :pending="sysPending(2)" :class="{ active: hmi.state.running }" title="整机启动（与现场物理启动二选一）" @click="systemCommand(2)">启动</Action>
        <Action v-if="hmi.state.paused" :icon="Play" :pending="sysPending(3, 4)" title="恢复（与现场物理恢复二选一）" @click="systemCommand(4)">恢复</Action>
        <Action v-else :icon="Pause" :pending="sysPending(3, 4)" title="暂停（与现场物理暂停二选一）" @click="systemCommand(3)">暂停</Action>
        <Action class="estop" :class="{ latched: hmi.state.estop }" :icon="hmi.state.estop ? Unlock : OctagonX" :pending="sysPending(10, 11)" :title="hmi.state.estop ? '解除急停（与现场物理解除二选一）' : '急停（与现场物理急停二选一）'" @click="systemCommand(hmi.state.estop ? 11 : 10)">{{ hmi.state.estop ? '解除急停' : '急停' }}</Action>
      </div>
      <div class="top-status"><Badge :tone="ready ? 'ok' : 'warn'">{{ ready ? '已连接' : '未连接' }}</Badge><span class="mono clock">{{ clock }}</span><Action :icon="Settings2" title="连接设置" aria-label="连接设置" @click="settings = true" /></div>
      <nav aria-label="主导航"><RouterLink v-for="link in links" :key="link.path" :to="link.path" :class="{ active: link.path === '/' ? route.path === '/' : route.path.startsWith(link.path) }" @click="jog.stop()"><component :is="link.icon" :size="18" /><span>{{ link.name }}</span></RouterLink></nav>
    </header>
    <div class="session-bar"><span class="connection-label"><span class="status-dot" :class="{ pulse: ready }" />{{ ready ? '状态流在线' : '状态流离线' }}<span class="muted">/</span><span>{{ route.meta.title }}</span></span>
      <div class="session-summary">
        <Badge class="machine-state" :tone="machine.tone" :title="`当前机器状态${hmi.state.manual ? ' · 手动模式' : ' · 自动模式'}`">{{ machine.label }}<span v-if="ready && hmi.state.manual" class="muted small">· 手动</span></Badge>
        <RouterLink v-if="conds.missing && ready" to="/" class="badge badge-warn cond-chip" title="查看自动运行缺失条件">{{ conds.missing }} 项启动条件未满足</RouterLink>
      </div>
      <div class="inline"><Badge v-if="hmi.state.mode === 'mock'" tone="warn">MOCK 模拟设备</Badge><span class="muted small">{{ hmi.state.mode === 'tcp' ? 'MODBUS TCP' : hmi.state.mode === 'mock' ? '模拟连接' : 'OFFLINE' }}</span><span class="mono small">{{ hmi.meta.version ? `V${hmi.meta.version}` : '' }}</span></div></div>
    <main class="content-area">
      <div :inert="!ready ? true : undefined" :aria-hidden="!ready ? true : undefined" class="view-content"><RouterView /></div>
      <div v-if="!ready" class="offline-overlay"><WifiOff :size="48" /><h1>{{ disconnectedTitle }}</h1><p>{{ hmi.state.error || '选择连接方式，完成握手后查看设备状态。' }}</p><Action :icon="Plug" primary @click="settings = true">连接设置</Action><span class="muted small">{{ hmi.state.connected ? '新的状态快照就绪后恢复' : '当前没有活动的设备连接' }}</span></div>
    </main>
    <footer class="statusbar"><span>急停不能替代硬件安全回路</span><span class="mono">{{ ready ? `快照 ${hmi.state.snapshot_epoch ?? '--'} · ACK ${hmi.state.ack_seq ?? '--'}` : '等待连接' }}</span></footer>
    <div class="toast-stack" aria-live="polite" aria-atomic="false"><div v-for="toast in hmi.toasts.slice(0, 4)" :key="toast.id" class="toast" :class="toast.good ? 'toast-ok' : 'toast-error'"><Check v-if="toast.good" :size="20" /><AlertTriangle v-else :size="20" /><div><strong>{{ toast.message }}</strong><small v-if="toast.detail">{{ toast.detail }}</small></div><button :aria-label="`关闭通知 ${toast.message}`" @click="hmi.toasts = hmi.toasts.filter(t => t.id !== toast.id)"><X :size="16" /></button></div></div>
    <div v-if="settings" class="modal-backdrop" @click.self="settings = false">
      <section class="modal connection-modal" role="dialog" aria-modal="true" aria-label="连接设置" @keydown.esc="settings = false">
        <header class="section-heading"><h2>连接设置</h2><Action :icon="X" aria-label="关闭" title="关闭" @click="settings = false" /></header>
        <form @submit.prevent="connect"><div class="segmented"><button type="button" :class="{ selected: mode === 'mock' }" @click="mode = 'mock'">模拟设备</button><button type="button" :class="{ selected: mode === 'tcp' }" @click="mode = 'tcp'">Modbus TCP</button></div>
          <Badge v-if="mode === 'mock'" tone="warn">MOCK · 不连接真实 PLC</Badge>
          <div v-else class="form-grid"><label class="full-field">PLC 地址<input v-model="host" required autocomplete="off" /></label><label>端口<input v-model="port" required type="number" min="1" max="65535" /></label><label>Unit ID<input v-model="unit" required type="number" min="1" max="247" /></label></div>
          <p v-if="hmi.state.error" class="error-text">{{ hmi.state.error }}</p>
          <footer class="modal-footer"><Action v-if="hmi.state.connected" :icon="Unplug" :pending="Boolean(hmi.pending.connect)" @click="disconnect">断开</Action><button type="submit" class="button primary" :disabled="hmi.pending.connect"><Plug :size="16" />{{ hmi.pending.connect ? '连接中' : '连接' }}</button></footer>
        </form>
      </section>
    </div>
  </div>
</template>
