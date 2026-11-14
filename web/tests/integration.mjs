import { chromium } from 'playwright'
import assert from 'node:assert/strict'

const url = process.env.HMI_URL || 'http://127.0.0.1:8765'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
const responseReads = []
const logResponse = response => {
  if (response.request().method() === 'POST') {
    responseReads.push(response.text().then(text => console.log(response.url(), response.status(), text.slice(0, 220))))
  }
}
page.on('response', logResponse)
const state = async () => (await page.request.get(`${url}/api/state`)).json()
const wait = async predicate => {
  for (let i = 0; i < 50; i++) { const current = await state(); if (predicate(current)) return current; await page.waitForTimeout(100) }
  console.log('Last events', JSON.stringify((await state()).events?.slice(0, 4)))
  const lastAxis = (await state()).axes?.[0]
  console.log('Last axis', JSON.stringify({
    position: lastAxis?.position, target: lastAxis?.target, running: lastAxis?.running,
    points: [lastAxis?.points?.[0], lastAxis?.points?.[1]],
  }))
  console.log('UI diagnostics', JSON.stringify(await page.evaluate(() => ({
    toasts: [...document.querySelectorAll('.toast')].map(node => node.textContent),
    busy: [...document.querySelectorAll('[aria-busy="true"]')].map(node => node.textContent),
    pointRow: document.querySelector('.points-table tbody tr')?.textContent,
  }))))
  await page.screenshot({ path: 'validation/integration-timeout.png' })
  throw new Error('State assertion timed out')
}
try {
  await page.goto(url)
  await page.getByText('设备未连接', { exact: true }).waitFor()
  await page.locator('.offline-overlay').getByRole('button', { name: '连接设置' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '连接', exact: true }).click()
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await wait(s => s.connected && s.handshake && s.mode === 'mock')
  await page.locator('.machine-state').filter({ hasText: '待复位' }).waitFor()
  await page.locator('.cond-chip').waitFor()
  assert.equal(await page.locator('.cond-item.missing').count(), 2, 'initial missing auto conditions')
  assert.equal(await page.getByText('PLC 启动许可', { exact: true }).count(), 0, 'PLC start permission condition removed')
  const controls = page.locator('.topbar .system-controls')
  assert.equal(await controls.getByRole('button', { name: '启动', exact: true }).isDisabled(), false, 'start is not pre-gated by PLC permit')
  await page.goto(`${url}/#/axes/0`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  assert.equal(await page.getByRole('button', { name: '使能', exact: true }).isDisabled(), false, 'axis enable is not pre-gated')
  assert.equal(await page.locator('.move-area').getByRole('button', { name: '执行', exact: true }).isDisabled(), false, 'motion is not pre-gated while PLC reports no permit')
  const meta = await (await page.request.get(`${url}/api/meta`)).json()
  for (const axis of [0, 1, 2]) {
    const pointResponse = await page.request.post(`${url}/api/point`, {
      headers: { 'X-CSRF-Token': meta.csrf_token },
      data: { axis, point: axis, position: 0, speed: 60, session: (await state()).session },
    })
    assert.equal(pointResponse.status(), 200, `teach P0 on axis ${axis}`)
    const current = await state()
    const configResponse = await page.request.post(`${url}/api/config`, {
      headers: { 'X-CSRF-Token': meta.csrf_token },
      data: { object_type: 3, object_index: axis, values: { flags: 3 }, epoch: current.config_epoch, session: current.session },
    })
    assert.equal(configResponse.status(), 200, `enable P0 on axis ${axis}`)
  }
  await wait(s => [0, 1, 2].every(axis => s.axes[axis].points[0].enabled && s.axes[axis].points[0].taught))
  await page.goto(`${url}/#/`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  const expectedEpoch = String((await state()).config_epoch)
  await page.waitForFunction(expected => {
    const item = [...document.querySelectorAll('.summary-item')].find(node => node.textContent.includes('配置版本'))
    return item?.querySelector('.mono')?.textContent === expected
  }, expectedEpoch)
  await page.getByRole('button', { name: '现场配置确认', exact: true }).click()
  await wait(s => s.configured && s.reset_required)
  await controls.getByRole('button', { name: '复位', exact: true }).click()
  await wait(s => !s.reset_required)
  await page.locator('.machine-state').filter({ hasText: '就绪' }).waitFor()
  assert.equal(await page.locator('.cond-chip').count(), 0, 'automatic conditions are met after confirmation and reset')
  assert.equal(await page.locator('.cond-item.missing').count(), 0, 'missing conditions after reset')
  await controls.getByRole('button', { name: '启动', exact: true }).click()
  await wait(s => s.running && !s.paused)
  await page.locator('.machine-state').filter({ hasText: '运行中' }).waitFor()
  assert.equal(await controls.getByRole('button', { name: '暂停', exact: true }).count(), 1, 'pause shown while running')
  await controls.getByRole('button', { name: '暂停', exact: true }).click()
  await wait(s => s.paused && !s.running)
  await page.locator('.machine-state').filter({ hasText: '已暂停' }).waitFor()
  await controls.getByRole('button', { name: '恢复', exact: true }).click()
  await wait(s => s.running && !s.paused)
  await page.getByRole('button', { name: '受控停全部', exact: true }).click()
  await wait(s => !s.running && !s.paused)
  await page.goto(`${url}/#/axes/0`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await page.getByRole('button', { name: '使能', exact: true }).click()
  await wait(s => s.axes[0].enabled)
  const jog = page.getByRole('button', { name: '正向点动', exact: true })
  const before = (await state()).axes[0].position
  await jog.dispatchEvent('pointerdown', { button: 0, pointerId: 1 })
  await page.waitForTimeout(650)
  await jog.dispatchEvent('pointerup', { pointerId: 1 })
  const stopped = await wait(s => s.axes[0].position > before && !s.axes[0].running)
  console.log(`Actual mock jog: ${before} -> ${stopped.axes[0].position}`)
  await page.waitForTimeout(250)
  await jog.dispatchEvent('pointerdown', { button: 0, pointerId: 1 })
  await page.waitForTimeout(350)
  await wait(s => s.axes[0].running)
  await page.evaluate(() => window.dispatchEvent(new Event('blur')))
  await wait(s => !s.axes[0].running)
  await page.getByRole('button', { name: '回原', exact: true }).click()
  await wait(s => s.axes[0].homed && !s.axes[0].running)
  await page.getByLabel('目标位置', { exact: true }).fill('12.345')
  await page.getByLabel('定位速度', { exact: true }).fill('20')
  await page.locator('.move-area').getByRole('button', { name: '执行', exact: true }).click()
  await wait(s => Math.abs(s.axes[0].position - 12.345) < .002 && !s.axes[0].running)
  await page.locator('.axis-readout .position-value.large').filter({ hasText: '12.345' }).waitFor()
  await page.locator('.points-table tbody tr').first().getByRole('button', { name: '示教', exact: true }).click()
  await wait(s => s.axes[0].points[0].taught && Math.abs(s.axes[0].points[0].position - 12.345) < .002)
  await page.getByLabel('启用 P0', { exact: true }).check()
  await wait(s => s.axes[0].points[0].enabled)
  await page.locator('.points-table tbody tr').first().getByRole('button', { name: '执行', exact: true }).click()
  await wait(s => !s.axes[0].running && Math.abs(s.axes[0].target - 12.345) < .002)
  // Axis 0 owns only its P0 slot; claim a free pool slot through the UI.
  await page.getByLabel('选择空闲点位槽', { exact: true }).selectOption({ label: 'P20' })
  await page.getByRole('button', { name: '示教并认领', exact: true }).click()
  await wait(s => s.points[20].owner === 0 && s.points[20].taught)
  await page.getByLabel('P20 位置', { exact: true }).fill('25.500')
  await page.getByLabel('P20 速度', { exact: true }).fill('12.000')
  await page.locator('.points-table tbody tr').nth(1).getByRole('button', { name: '写入', exact: true }).click()
  await wait(s => s.points[20].position === 25.5 && s.points[20].speed === 12)
  await page.getByRole('button', { name: '轴参数', exact: true }).click()
  await page.getByLabel('手动速度', { exact: true }).fill('15')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  await wait(s => s.axes[0].config.manual_speed === 15)
  await page.getByRole('button', { name: '修改轴名称', exact: true }).click()
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('测试轴')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  await wait(s => s.axes[0].name === '测试轴')
  // Point and axis writes invalidate configuration confirmation. Reconfirm the
  // latest epoch and finish reset before requesting either cylinder direction.
  await page.goto(`${url}/#/`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  const cylinderEpoch = String((await state()).config_epoch)
  await page.waitForFunction(expected => {
    const item = [...document.querySelectorAll('.summary-item')].find(node => node.textContent.includes('配置版本'))
    return item?.querySelector('.mono')?.textContent === expected
  }, cylinderEpoch)
  await page.getByRole('button', { name: '现场配置确认', exact: true }).click()
  await wait(s => s.configured)
  await controls.getByRole('button', { name: '复位', exact: true }).click()
  await wait(s => s.configured && !s.reset_required && !s.resetting && !s.running && !s.paused && s.manual && !s.cylinders[0].moving)
  await page.goto(`${url}/#/cylinders`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await page.locator('.cylinder-table tbody tr').first().getByRole('button', { name: '动点', exact: true }).click()
  await wait(s => s.cylinders[0].move && !s.cylinders[0].moving)
  await page.locator('.cylinder-table tbody tr').first().getByRole('button', { name: '原点', exact: true }).click()
  await wait(s => s.cylinders[0].home && !s.cylinders[0].moving)
  await page.locator('.cylinder-table tbody tr').first().getByTitle('气缸参数', { exact: true }).click()
  await page.getByLabel('动点确认延时', { exact: true }).fill('250')
  await page.getByLabel('原点确认延时', { exact: true }).fill('450')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  await wait(s => s.cylinders[0].config.delay_ms === 250 && s.cylinders[0].config.home_delay_ms === 450)
  await page.locator('.cylinder-table tbody tr').first().getByTitle('修改名称', { exact: true }).click()
  await page.getByRole('dialog').getByLabel('名称', { exact: true }).fill('测试气缸')
  await page.getByRole('button', { name: '提交并读回', exact: true }).click()
  await wait(s => s.cylinders[0].name === '测试气缸')
  for (const viewport of [{ width: 1280, height: 800 }, { width: 1024, height: 640 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport)
    for (const [route, label] of [['/', 'overview'], ['/axes/0', 'axes'], ['/cylinders', 'cylinders'], ['/io', 'io'], ['/diagnostics', 'diagnostics']]) {
      await page.goto(`${url}/#${route}`)
      await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
      await page.waitForTimeout(120)
      while (await page.locator('.toast button').count()) await page.locator('.toast button').first().click()
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
      await page.screenshot({ path: `validation/actual-${label}-${viewport.width}.png` })
    }
  }
  await page.goto(`${url}/#/diagnostics`)
  await page.locator('.offline-overlay').waitFor({ state: 'hidden' })
  await page.screenshot({ path: 'validation/integration-diagnostics.png' })
  await page.locator('.estop').click()
  await wait(s => s.estop)
  await page.locator('.machine-state').filter({ hasText: '急停' }).waitFor()
  await controls.getByRole('button', { name: '解除急停', exact: true }).click()
  await wait(s => !s.estop)
  // Axis/point writes earlier in this run clear configuration confirmation, so a new reset is required.
  await page.locator('.machine-state').filter({ hasText: '待复位' }).waitFor()
  assert.deepEqual(errors, [])
  console.log('Actual backend mock checks passed: connect, enable, jog release/blur, home, scaled move, teach, point write/enable/execute, axis and cylinder config/name, cylinder actions, diagnostics, software estop; 15 responsive screenshots captured.')
} finally {
  try {
    const meta = await (await page.request.get(`${url}/api/meta`)).json()
    await page.request.post(`${url}/api/disconnect`, { headers: { 'X-CSRF-Token': meta.csrf_token }, data: {} })
  } finally {
    page.off('response', logResponse)
    try { await Promise.all(responseReads) } finally { await browser.close() }
  }
}
