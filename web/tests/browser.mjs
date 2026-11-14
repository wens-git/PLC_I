import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'

const baseURL = process.env.HMI_URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const requests = []
const offline = { connected: false, handshake: false, mode: 'offline', session: '', axes: [], cylinders: [], events: [], io: { x: [], y: [] }, global_permit: 0, global_reason: 2, estop: false, software_estop: false, alarm: false, resetting: false, running: false, paused: false, reset_required: false, manual: false, configured: false, flow_ready: false }
let state = offline
const connected = {
  connected: true, handshake: true, mode: 'mock', session: 'browser-test-session', config_epoch: 1,
  global_permit: 1 | (1 << 4), global_reason: 11, manual: true, configured: false, heartbeat: 88, snapshot_epoch: 100, ack_seq: 0,
  estop: false, software_estop: false, alarm: false, resetting: false, running: false, paused: false, reset_required: true, flow_ready: true,
  axes: Array.from({ length: 16 }, (_, index) => ({ index, name: `轴 ${index}`, bound: index < 3, online: index < 3, enabled: true, homed: false, running: false, position: index * 25, velocity: 0, target: 0, permit: 0, reason: index < 3 ? 0 : 4,
    config: { positive_limit: 500, negative_limit: -500, manual_speed: 10, auto_speed: 20, acceleration: 100, deceleration: 100, estop_deceleration: 200, flags: 1 },
    points: Array.from({ length: 20 }, (_, index) => ({ index, name: `点位 ${index}`, position: index * 10, speed: 10, enabled: false, taught: true })),
  })),
  cylinders: Array.from({ length: 54 }, (_, index) => ({ index, name: `气缸 ${index}`, bound: index < 12, online: index < 12, home: true, move: false, moving: false, permit: 0, reason: index < 12 ? 0 : 4, config: { wiring_flags: index % 4, move_y: index, home_y: index % 2 ? index + 1 : 65535, move_x: index, home_x: 65535, delay_ms: 200, home_delay_ms: 300, timeout_ms: 3000 } })),
  events: [{ time: new Date().toISOString(), result: 0, message: '测试设备已连接', seq: 1 }],
  io: { x: Array.from({ length: 32 }, (_, i) => i % 3 === 0), y: Array(32).fill(false) },
  raw: { status: Array.from({ length: 104 }, (_, index) => index), axis_live: Array(256).fill(0) },
}
await page.route('**/api/**', async route => {
  const url = new URL(route.request().url())
  let response
  if (url.pathname === '/api/meta') response = { csrf_token: 'test-token', version: 'test', rejections: [{ code: 0, message: '按 PLC 许可执行' }, { code: 4, message: '对象未绑定' }] }
  else if (url.pathname === '/api/state') response = state
  else {
    const body = route.request().postDataJSON()
    assert.equal(route.request().headers()['x-csrf-token'], 'test-token')
    requests.push({ path: url.pathname, body })
    if (url.pathname === '/api/connect') { assert.equal(body.mode, 'mock'); state = structuredClone(connected) }
    if (url.pathname === '/api/disconnect') state = offline
    if (url.pathname === '/api/command') {
      const { code } = body
      if (code === 1) {
        state = { ...state, resetting: true }
        setTimeout(() => { state = { ...state, resetting: false, reset_required: false, global_permit: state.global_permit | (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7), global_reason: 0 } }, 300)
      }
      if (code === 2) state = { ...state, running: true, paused: false, manual: false }
      if (code === 3) state = { ...state, running: false, paused: true, manual: true }
      if (code === 4) state = { ...state, running: true, paused: false, manual: false }
      if (code === 10) state = { ...state, estop: true, software_estop: true, running: false, paused: false, global_permit: state.global_permit | (1 << 8) }
      if (code === 11) state = { ...state, estop: false, software_estop: false }
    }
    response = { result: 0, message: '已受理', seq: requests.length }
  }
  await route.fulfill({ json: response })
})
await page.routeWebSocket('**/ws', ws => {
  const timer = setInterval(() => ws.send(JSON.stringify({ type: 'snapshot', state })), 100)
  timer.unref()
  ws.onClose(() => clearInterval(timer))
})
await mkdir('validation', { recursive: true })
try {
  await page.goto(baseURL)
  const theme = await page.evaluate(() => ({
    colorScheme: getComputedStyle(document.documentElement).colorScheme,
    background: getComputedStyle(document.documentElement).backgroundColor,
  }))
  const [r, g, b] = theme.background.match(/\d+/g).map(Number)
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
  assert.ok(luminance > 0.7, `theme is not light, background: ${theme.background}`)
  assert.equal(theme.colorScheme, 'light')
  await page.getByText('设备未连接', { exact: true }).waitFor()
  await page.screenshot({ path: 'validation/offline-1280.png' })
  await page.locator('.offline-overlay').getByRole('button', { name: '连接设置' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '连接', exact: true }).click()
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await page.getByText('MOCK 模拟设备', { exact: true }).waitFor()
  await page.locator('.toast button').first().click()
  const controls = page.locator('.topbar .system-controls')
  await page.locator('.machine-state').filter({ hasText: '待复位' }).waitFor()
  await page.locator('.cond-chip').filter({ hasText: '2' }).waitFor()
  await page.locator('.cond-item.missing').first().waitFor()
  assert.equal(await page.locator('.cond-item.missing').count(), 2, 'initial missing auto conditions')
  assert.equal(await page.getByText('PLC 启动许可', { exact: true }).count(), 0, 'PLC start permission condition removed')
  assert.equal(await page.getByRole('button', { name: '复位', exact: true }).count(), 1, 'only one reset button')
  assert.deepEqual(await controls.getByRole('button').allTextContents(), ['复位', '启动', '暂停', '急停'])
  assert.equal(await controls.getByRole('button', { name: '启动', exact: true }).isDisabled(), false, 'start is not pre-gated by PLC permit')
  await controls.getByRole('button', { name: '复位', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '复位中' }).waitFor({ timeout: 250 })
  await page.locator('.machine-state').filter({ hasText: '就绪' }).waitFor()
  await page.locator('.cond-chip').filter({ hasText: '1' }).waitFor()
  assert.equal(await page.locator('.cond-item.missing').count(), 1, 'missing conditions after reset')
  await controls.getByRole('button', { name: '启动', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '运行中' }).waitFor()
  assert.ok(await controls.getByRole('button', { name: '启动', exact: true }).evaluate(el => el.classList.contains('active')), 'start button active while running')
  await controls.getByRole('button', { name: '暂停', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '已暂停' }).waitFor()
  assert.deepEqual(await controls.getByRole('button').allTextContents(), ['复位', '启动', '恢复', '急停'])
  await controls.getByRole('button', { name: '恢复', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '运行中' }).waitFor()
  assert.deepEqual(await controls.getByRole('button').allTextContents(), ['复位', '启动', '暂停', '急停'])
  await controls.getByRole('button', { name: '暂停', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '已暂停' }).waitFor()
  for (const viewport of [{ width: 1280, height: 800 }, { width: 1024, height: 640 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    for (const [route, label] of [['/', 'overview'], ['/axes/0', 'axes'], ['/cylinders', 'cylinders'], ['/io', 'io'], ['/diagnostics', 'diagnostics']]) {
      await page.goto(`${baseURL}/#${route}`)
      await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
      await page.waitForTimeout(200)
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `overflow ${label} ${viewport.width}`)
      const controlBox = await controls.boundingBox()
      assert.ok(controlBox && Math.abs((controlBox.x + controlBox.width / 2) - viewport.width / 2) < 8, `system controls centered ${label} ${viewport.width}`)
      const stop = await page.locator('.estop').boundingBox()
      assert.ok(stop.height >= 40 && stop.width >= 64 && stop.x + stop.width <= viewport.width, `estop visible ${label} ${viewport.width}`)
      await page.screenshot({ path: `validation/${label}-${viewport.width}.png` })
    }
  }
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto(`${baseURL}/#/axes/0`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  for (const name of ['使能', '去使能', '回原', '清故障', '位置置零', '轴参数', '修改轴名称']) {
    assert.equal(await page.getByRole('button', { name, exact: true }).isDisabled(), false, `${name} is not pre-gated by PLC permit`)
  }
  assert.equal(await page.locator('.jog-buttons').getByRole('button', { name: '正向点动', exact: true }).isDisabled(), false, 'positive jog is not pre-gated')
  assert.equal(await page.locator('.move-area').getByRole('button', { name: '执行', exact: true }).isDisabled(), false, 'motion is not pre-gated')
  const pointRow = page.locator('.points-table tbody tr').first()
  for (const name of ['示教', '写入', '执行']) assert.equal(await pointRow.getByRole('button', { name, exact: true }).isDisabled(), false, `point ${name} is not pre-gated`)
  await page.goto(`${baseURL}/#/cylinders`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  const cylinderRow = page.locator('.cylinder-table tbody tr').first()
  for (const name of ['动点', '原点', '取消']) assert.equal(await cylinderRow.getByRole('button', { name, exact: true }).isDisabled(), false, `cylinder ${name} is not pre-gated`)
  assert.match(await cylinderRow.textContent(), /原点 · 延时完成/)
  const vacuumRow = page.locator('.cylinder-table tbody tr').nth(2)
  assert.equal(await vacuumRow.getByRole('button', { name: '吸附', exact: true }).count(), 1)
  assert.equal(await vacuumRow.getByRole('button', { name: '释放', exact: true }).count(), 1)
  await cylinderRow.getByTitle('气缸参数', { exact: true }).click()
  const cylinderDialog = page.getByRole('dialog')
  assert.equal(await cylinderDialog.getByText('调试屏蔽', { exact: true }).count(), 0)
  assert.match(await cylinderDialog.textContent(), /工程配置（只读）/)
  await cylinderDialog.getByLabel('动点确认延时', { exact: true }).fill('250')
  await cylinderDialog.getByLabel('原点确认延时', { exact: true }).fill('0')
  await cylinderDialog.getByRole('button', { name: '提交并读回', exact: true }).click()
  await cylinderDialog.getByRole('alert').filter({ hasText: '无传感器' }).waitFor()
  await cylinderDialog.getByLabel('原点确认延时', { exact: true }).fill('450')
  await cylinderDialog.getByRole('button', { name: '提交并读回', exact: true }).click()
  await cylinderDialog.waitFor({ state: 'hidden' })
  assert.deepEqual(requests.find(r => r.path === '/api/config' && r.body.object_type === 2).body.values,
    { delay_ms: 250, home_delay_ms: 450, timeout_ms: 3000 })
  await page.goto(`${baseURL}/#/axes/0`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await page.getByLabel('目标位置', { exact: true }).fill('12.345')
  await page.getByLabel('定位速度', { exact: true }).fill('5.000')
  await page.locator('.move-area').getByRole('button', { name: '执行', exact: true }).click()
  await page.waitForTimeout(150)
  assert.ok(requests.some(r => r.path === '/api/command' && r.body.code === 27 && r.body.a === 12345 && r.body.b === 5000))
  const jog = page.getByRole('button', { name: '正向点动', exact: true })
  await jog.dispatchEvent('pointerdown', { button: 0, pointerId: 1 })
  await page.waitForTimeout(450)
  await jog.dispatchEvent('pointerup', { pointerId: 1 })
  await page.waitForTimeout(150)
  const start = requests.find(r => r.path === '/api/jog/start')
  assert.ok(start?.body.token)
  assert.ok(requests.some(r => r.path === '/api/jog/renew' && r.body.token === start.body.token))
  assert.ok(requests.some(r => r.path === '/api/jog/stop' && r.body.token === start.body.token))
  await page.getByRole('button', { name: '轴参数', exact: true }).click()
  const limit = page.getByLabel('软正限位', { exact: true })
  await limit.fill('600.000')
  await page.waitForTimeout(350)
  assert.equal(await limit.inputValue(), '600.000', 'snapshot does not overwrite editor')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  await page.waitForTimeout(100)
  assert.ok(requests.some(r => r.path === '/api/config' && r.body.values.positive_limit === 600))
  await page.getByLabel('启用 P0', { exact: true }).check()
  await page.waitForTimeout(100)
  assert.ok(requests.some(r => r.path === '/api/config' && r.body.object_type === 3 && r.body.values.flags === 3))
  await page.getByRole('button', { name: '修改轴名称', exact: true }).click()
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('测试轴')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  assert.ok(requests.some(r => r.path === '/api/name' && r.body.name === '测试轴'))
  await page.locator('.points-table tbody tr').first().getByRole('button', { name: '示教', exact: true }).click()
  await page.waitForTimeout(100)
  assert.ok(requests.some(r => r.path === '/api/point' && r.body.position === 0 && r.body.speed === 10))
  await page.locator('.estop').click()
  await page.locator('.machine-state').filter({ hasText: '急停' }).waitFor()
  await controls.getByRole('button', { name: '解除急停', exact: true }).click()
  await page.locator('.machine-state').filter({ hasText: '就绪' }).waitFor()
  assert.deepEqual(errors, [])
  console.log(`Browser checks passed; ${requests.length} API writes verified; 16 screenshots captured at 1280, 1024, and 390 widths.`)
} finally { await browser.close() }
