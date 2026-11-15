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
export function cylinderAction(config, code) {
  const mode = Number.isInteger(config?.wiring_flags) ? config.wiring_flags & 3 : null
  if (mode === null) return { label: code === 40 ? '到动点 / 吸附' : code === 41 ? '到原点 / 释放' : '撤销命令', title: '阀型配置未读回，请核验阀型及输出行为；撤销命令不等于机械停止。' }
  const vacuum = mode >= 2
  const timeout = '真空超时应保持吸附，需手动释放；PLC 同时报警。'
  if (code === 40) return { label: vacuum ? '吸附' : '到动点', title: vacuum ? `开启吸气并等待吸附确认；${timeout}` : '驱动到动点，完成后保持动点输出。' }
  if (code === 41) return { label: vacuum ? '释放' : '到原点', title: vacuum ? `${mode === 3 ? '关闭吸气并开启破真空，释放完成后关闭破真空。' : '关闭吸气并等待释放确认。'}${timeout}` : mode === 0 ? '关闭动点输出，由弹簧复位回原点。' : '关闭动点输出并驱动原点输出，到原点后保持原点输出。' }
  if (mode === 0) return { label: '断电回原点', title: '撤销本次命令并关闭两路输出，阀弹簧复位使气缸回原点；不是保持当前位置或安全急停。' }
  if (mode === 1) return { label: '撤销命令（阀保持，不会停止动作）', title: '撤销本次命令并关闭两路输出；双电控阀保持原阀位，不会停止动作，也不会主动回原点。' }
  return { label: '释放（关吸气）', title: `撤销本次命令，关闭吸气及破真空输出；不执行破真空释放计时。${timeout}` }
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
