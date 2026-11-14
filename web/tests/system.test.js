import { test } from 'node:test'
import assert from 'node:assert/strict'
import { machineState, autoConditions } from '../src/system.js'

const base = { connected: true, handshake: true, estop: false, alarm: false, resetting: false,
  running: false, reset_required: false, manual: false, configured: true, flow_ready: true, global_permit: 0 }

test('machine state priority: offline, estop, alarm, resetting, running, reset_required, ready', () => {
  assert.equal(machineState({ ...base, connected: false }).label, '离线')
  assert.equal(machineState({ ...base, estop: true }).label, '急停')
  assert.equal(machineState({ ...base, alarm: true }).label, '报警')
  assert.equal(machineState({ ...base, resetting: true }).label, '复位中')
  assert.equal(machineState({ ...base, running: true }).label, '运行中')
  assert.equal(machineState({ ...base, paused: true }).label, '已暂停')
  assert.equal(machineState({ ...base, reset_required: true }).label, '待复位')
  assert.equal(machineState(base).label, '就绪')
  const tones = { 离线: 'neutral', 急停: 'danger', 报警: 'danger', 复位中: 'warn', 待复位: 'warn', 运行中: 'ok', 已暂停: 'warn', 就绪: 'ok' }
  for (const [label, tone] of Object.entries(tones)) assert.equal(machineState({ ...base, connected: label !== '离线', estop: label === '急停', alarm: label === '报警', resetting: label === '复位中', running: label === '运行中', paused: label === '已暂停', reset_required: label === '待复位' }).tone, tone)
})

test('auto conditions list every gate with met flag and counts missing items', () => {
  const state = { ...base, configured: false, flow_ready: false, reset_required: true, global_permit: 0 }
  const list = autoConditions(state)
  assert.deepEqual(list.filter(item => !item.met).map(item => item.label),
    ['现场配置已确认', '复位完成（无待复位）', '正式流程已接入'])
  const allMet = autoConditions(base)
  assert.ok(allMet.every(item => item.met))
  assert.equal(allMet.missing, 0)
  assert.equal(list.missing, 3)
})

test('auto conditions treat offline and estop as blocking with detail text', () => {
  const list = autoConditions({ ...base, connected: false, estop: true })
  assert.ok(list.find(item => item.label === '设备连接与握手' && !item.met))
  assert.ok(list.find(item => item.label === '无急停' && !item.met))
  assert.equal(list.missing, 2)
})
