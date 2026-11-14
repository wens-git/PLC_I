<script setup>
import { computed } from 'vue'
import { Activity, ShieldCheck, TriangleAlert, History, Square, CheckCheck, ArrowUpRight, Check, X } from 'lucide-vue-next'
import { hmi, command, reason } from '../store'
import { machineState, autoConditions } from '../system'
import { number } from '../protocol'
import { cylinderStatus } from '../cylinder'
import Badge from '../components/Badge.vue'
import Action from '../components/Action.vue'
const alarms = computed(() => [...hmi.state.axes, ...hmi.state.cylinders].filter(item => item.alarm).length)
const machine = computed(() => machineState(hmi.state))
const conds = computed(() => autoConditions(hmi.state))
const permitReason = computed(() => {
  if (hmi.state.global_permit || Number(hmi.state.global_reason)) return reason(hmi.state.global_reason)
  return 'PLC 未发布闭锁原因'
})
</script>
<template>
  <div class="page">
    <div class="page-heading"><div><p class="eyebrow">设备监控</p><h1>运行总览</h1></div><Badge :tone="machine.tone">{{ machine.label }}</Badge></div>
    <section class="summary-grid" aria-label="系统状态">
      <div class="summary-item"><Activity /><span>通信健康</span><strong>{{ hmi.state.handshake ? '握手完成' : '等待握手' }}</strong><small class="mono">HEARTBEAT {{ hmi.state.heartbeat ?? '--' }}</small></div>
      <div class="summary-item"><ShieldCheck /><span>全局动作许可</span><strong>{{ hmi.state.global_permit ? '许可已发布' : '动作闭锁' }}</strong><small>{{ permitReason }}</small></div>
      <div class="summary-item"><TriangleAlert /><span>当前报警对象</span><strong class="mono" :class="{ 'error-text': alarms }">{{ alarms }}<small> 个</small></strong><small>首报警 {{ hmi.state.first_alarm || '--' }}</small></div>
      <div class="summary-item"><History /><span>配置版本</span><strong class="mono">{{ hmi.state.config_epoch ?? '--' }}</strong><small>{{ hmi.state.configured ? '现场配置已确认' : '现场配置待确认' }}</small></div>
    </section>
    <section class="section-block"><header class="section-heading"><h2>自动运行条件</h2><span class="muted small">{{ conds.missing ? `${conds.missing} 项未满足 · 逐项排除后重试启动` : '全部满足 · 可整机启动' }}</span></header>
      <ul class="cond-list">
        <li v-for="item in conds" :key="item.label" class="cond-item" :class="{ missing: !item.met }">
          <Check v-if="item.met" :size="16" /><X v-else :size="16" />
          <span>{{ item.label }}</span>
          <small :class="item.met ? 'muted' : 'warn-text'">{{ item.met ? '满足' : item.detail }}</small>
        </li>
      </ul>
    </section>
    <section class="section-block"><header class="section-heading"><h2>系统命令</h2><span class="muted small">{{ hmi.state.manual ? '手动模式' : '自动模式' }}</span></header><div class="action-row"><Action :icon="CheckCheck" :pending="Boolean(hmi.pending['command:52:0:0'])" title="现场配置确认" @click="command(52, 0, 0, hmi.state.config_epoch)">现场配置确认</Action><Action :icon="Square" :pending="Boolean(hmi.pending['command:9:0:0'])" @click="command(9)">受控停全部</Action></div></section>
    <section class="section-block"><header class="section-heading"><h2>轴实时状态</h2><RouterLink to="/axes" class="text-link">全部轴 <ArrowUpRight :size="16" /></RouterLink></header><div class="axis-grid"><RouterLink v-for="axis in hmi.state.axes" :key="axis.index" :to="`/axes/${axis.index}`" class="axis-card"><div class="section-heading"><span class="object-name">{{ axis.name }}</span><span class="muted mono small">AX{{ axis.index }}</span></div><div class="position-value">{{ axis.bound ? number(axis.position) : '--' }}<span>{{ axis.unit || 'mm' }}</span></div><div class="section-heading"><Badge :tone="axis.alarm ? 'danger' : !axis.bound ? 'neutral' : axis.online ? 'ok' : 'warn'">{{ !axis.bound ? '未绑定' : axis.alarm ? '报警' : axis.online ? '在线' : '离线' }}</Badge><span class="mono small muted">{{ axis.bound ? `${number(axis.velocity)} ${axis.unit || 'mm'}/s` : '未分配' }}</span></div></RouterLink></div></section>
    <section class="section-block"><header class="section-heading"><h2>气缸状态 <span class="muted small">{{ hmi.state.cylinders.filter(c => c.bound).length }} / {{ hmi.state.cylinders.length }} 已绑定</span></h2><div class="inline small"><Badge tone="ok">原点 / 释放确认</Badge><Badge tone="warn">动点 / 吸附 / 动作中</Badge><Badge tone="danger">报警</Badge></div></header><div class="cylinder-map"><RouterLink v-for="cylinder in hmi.state.cylinders" :key="cylinder.index" :to="`/cylinders/${cylinder.index}`" :title="`${cylinder.name} · ${cylinderStatus(cylinder)}`" class="cylinder-cell mono" :class="!cylinder.bound ? 'unbound' : cylinder.alarm ? 'fault' : cylinder.home ? 'home' : 'move'">{{ String(cylinder.index).padStart(2, '0') }}</RouterLink></div></section>
  </div>
</template>
