const types = ['单线圈弹簧复位', '双线圈保持', '真空吸附', '真空吸附 + 破真空']
export function cylinderType(config) {
  return Number.isInteger(config?.wiring_flags) ? types[config.wiring_flags & 3] : '配置未读回'
}
export function cylinderSide(config, side) {
  const vacuum = Number.isInteger(config?.wiring_flags) && (config.wiring_flags & 3) >= 2
  const label = side === 'move' ? (vacuum ? '吸附' : '动点') : (vacuum ? '释放' : '原点')
  const address = config?.[`${side}_x`]
  const known = Number.isInteger(address)
  const sensor = known && address !== 65535
  const inverted = sensor && Boolean(config.wiring_flags & (side === 'move' ? 4 : 8))
  return { label, sensor, known, confirmation: !known ? '配置未读回' : sensor ? '传感器确认' : '延时完成',
    input: !known ? '配置未读回' : sensor ? `X${address}${inverted ? '（反相）' : ''}` : '无传感器' }
}
export function cylinderStatus(cylinder) {
  if (cylinder.alarm) return '故障'
  if (cylinder.moving) return '动作中'
  const confirmed = ['move', 'home'].filter(side => cylinder[side]).map(side => {
    const info = cylinderSide(cylinder.config, side)
    return `${info.label} · ${info.confirmation}`
  })
  return confirmed.join(' / ') || '未确认'
}
export function cylinderValues(form, config) {
  const values = {}
  for (const field of ['delay_ms', 'home_delay_ms', 'timeout_ms']) {
    const text = String(form[field] ?? '').trim()
    if (!/^\d+$/.test(text)) throw new Error('延时和超时须填写整数毫秒')
    values[field] = Number(text)
  }
  if (values.timeout_ms < 1 || values.timeout_ms > 65535 ||
      [values.delay_ms, values.home_delay_ms].some(value => value < 0 || value > 65534 || value >= values.timeout_ms)) {
    throw new Error('两侧延时为 0..65534 ms，总超时为 1..65535 ms，且两侧延时都必须小于总超时')
  }
  for (const [side, field] of [['move', 'delay_ms'], ['home', 'home_delay_ms']]) {
    const info = cylinderSide(config, side)
    if (!info.known) throw new Error('传感器配置尚未完整读回，无法提交')
    if (!info.sensor && values[field] === 0) throw new Error(`${info.label}无传感器，确认延时必须大于 0 ms`)
  }
  return values
}
