export function scaled(value, unsigned = false) {
  const text = String(value).trim()
  if (!/^-?\d+(?:\.\d{1,3})?$/.test(text)) throw new Error('请输入最多三位小数的有效数值')
  const result = Math.round(Number(text) * 1000)
  if (!Number.isSafeInteger(result) || result > 2147483647 || result < (unsigned ? 1 : -2147483648)) {
    throw new Error(unsigned ? '数值范围为 0.001 至 2147483.647' : '数值范围为 -2147483.648 至 2147483.647')
  }
  return result
}
export const NAME_MAX = 32
const REPLACEMENT = String.fromCharCode(0xFFFD)
export function validName(value) {
  let loneSurrogate = false
  for (let i = 0; i < (value?.length || 0); i++) {
    const unit = value.charCodeAt(i)
    if (unit >= 0xD800 && unit <= 0xDBFF) {
      const next = i + 1 < value.length ? value.charCodeAt(i + 1) : 0
      if (next < 0xDC00 || next > 0xDFFF) { loneSurrogate = true; break }
      i++
    } else if (unit >= 0xDC00 && unit <= 0xDFFF) { loneSurrogate = true; break }
  }
  // Names are host metadata (protocol 1.2): limit by characters, not PLC registers.
  const text = value?.trim() || ''
  const control = [...text].some(ch => ch.codePointAt(0) < 32)
  if (!text || [...text].length > NAME_MAX || loneSurrogate || control || text.includes(REPLACEMENT)) {
    throw new Error(`名称须为 1 至 ${NAME_MAX} 个字符，且不能含控制字符、替换符或孤立代理项`)
  }
  return text
}
export function number(value, digits = 3) { return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '--' }
export function hex(value, width = 4) { return Number(value ?? 0).toString(16).toUpperCase().padStart(width, '0') }
