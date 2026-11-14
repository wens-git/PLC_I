import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cylinderType, cylinderSide, cylinderStatus, cylinderValues } from '../src/cylinder.js'

const config = { wiring_flags: 0, move_y: 0, home_y: 65535, move_x: 0, home_x: 65535, delay_ms: 0, home_delay_ms: 200, timeout_ms: 3000 }
test('all wiring modes display engineering type and vacuum action labels', () => {
  for (const [mode, type] of ['单线圈弹簧复位', '双线圈保持', '真空吸附', '真空吸附 + 破真空'].entries()) {
    const c = { ...config, wiring_flags: mode }
    assert.equal(cylinderType(c), type)
    assert.equal(cylinderSide(c, 'move').label, mode >= 2 ? '吸附' : '动点')
    assert.equal(cylinderSide(c, 'home').label, mode >= 2 ? '释放' : '原点')
  }
})
test('sensor confirmation and time completion are separate, including inversion', () => {
  assert.equal(cylinderSide(config, 'move').input, 'X0')
  assert.equal(cylinderSide({ ...config, wiring_flags: 12 }, 'move').input, 'X0（反相）')
  assert.equal(cylinderSide({ ...config, wiring_flags: 12 }, 'home').input, '无传感器')
  assert.equal(cylinderStatus({ config, move: true }), '动点 · 传感器确认')
  assert.equal(cylinderStatus({ config, home: true }), '原点 · 延时完成')
  assert.equal(cylinderStatus({ config }), '未确认')
  assert.equal(cylinderStatus({ config, home: true, moving: true }), '动作中')
  assert.equal(cylinderStatus({ config, home: true, alarm: true }), '故障')
  assert.equal(cylinderSide(undefined, 'home').confirmation, '配置未读回')
})
test('only the three time parameters are submitted, preserving independent delays', () => {
  assert.deepEqual(cylinderValues(config, config), { delay_ms: 0, home_delay_ms: 200, timeout_ms: 3000 })
  assert.deepEqual(cylinderValues({ ...config, delay_ms: '12', home_delay_ms: '34' }, config), { delay_ms: 12, home_delay_ms: 34, timeout_ms: 3000 })
})
test('both delays obey total timeout and absent sensors require a positive delay', () => {
  for (const field of ['delay_ms', 'home_delay_ms']) {
    for (const value of ['', ' ', null, -1, 1.5, '1e2', 3000, 65535]) {
      assert.throws(() => cylinderValues({ ...config, [field]: value }, config))
    }
  }
  for (const value of [0, 65536, '', 1.5]) assert.throws(() => cylinderValues({ ...config, timeout_ms: value }, config))
  assert.throws(() => cylinderValues({ ...config, home_delay_ms: 0 }, config), /无传感器/)
  assert.throws(() => cylinderValues(config, { ...config, move_x: 65535 }), /无传感器/)
  assert.throws(() => cylinderValues(config, {}), /未完整读回/)
  assert.deepEqual(cylinderValues({ delay_ms: 65534, home_delay_ms: 65534, timeout_ms: 65535 }, config), { delay_ms: 65534, home_delay_ms: 65534, timeout_ms: 65535 })
  assert.equal(cylinderValues({ ...config, home_delay_ms: 0 }, { ...config, home_x: 1 }).home_delay_ms, 0)
})
