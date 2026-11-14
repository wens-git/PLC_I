export function machineState(state) {
  if (!state.connected || !state.handshake) return { label: '离线', tone: 'neutral' }
  if (state.estop) return { label: '急停', tone: 'danger' }
  if (state.alarm) return { label: '报警', tone: 'danger' }
  if (state.resetting) return { label: '复位中', tone: 'warn' }
  if (state.running) return { label: '运行中', tone: 'ok' }
  if (state.paused) return { label: '已暂停', tone: 'warn' }
  if (state.reset_required) return { label: '待复位', tone: 'warn' }
  return { label: '就绪', tone: 'ok' }
}

export function autoConditions(state) {
  const list = [
    { label: '设备连接与握手', met: Boolean(state.connected && state.handshake), detail: '设备未连接或握手未完成' },
    { label: '无急停', met: !state.estop, detail: '急停有效，先解除急停并复位' },
    { label: '现场配置已确认', met: Boolean(state.configured), detail: '确认后需执行全局复位' },
    { label: '复位完成（无待复位）', met: !state.reset_required, detail: '上电或配置确认后需全局复位' },
    { label: '无活动报警', met: !state.alarm, detail: '先排除并清除报警' },
    { label: '正式流程已接入', met: Boolean(state.flow_ready), detail: '未接入时整机启动被拒绝' },
  ]
  list.missing = list.filter(item => !item.met).length
  return list
}
