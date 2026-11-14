import { chromium } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'

const base = process.env.HMI_URL || 'http://127.0.0.1:5178'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
const writes = []
const errors = []
page.on('pageerror', error => errors.push(error.message))
const point = { index: 2, name: '点位 2', position: 0, speed: 0.001, enabled: false, taught: false, owner: 2 }
const state = {
  connected: true, handshake: true, mode: 'mock', session: 'layout-test', config_epoch: 4,
  manual: true, global_permit: 0, global_reason: 0, events: [], alarms: [],
  names_revision: 0, points: [point, { index: 16, owner: null }], cylinders: [],
  io: { x: [], y: [] },
  axes: [{ index: 2, name: '轴 2', online: true, bound: true, position: 12.345,
    velocity: 0, target: 0, permit: 0, reason: 0, points: [point], config: { manual_speed: 5 } }],
}
await page.route('**/api/**', async route => {
  const path = new URL(route.request().url()).pathname
  if (route.request().method() !== 'GET') writes.push({ path, body: route.request().postDataJSON() })
  await route.fulfill({ json: path === '/api/meta'
    ? { csrf_token: 'test', version: 'test', rejections: [] }
    : path === '/api/state' ? state : { result: 0, message: 'ok' } })
})
await page.routeWebSocket('**/ws', ws => {
  ws.send(JSON.stringify({ type: 'snapshot', state }))
})
try {
  await mkdir('validation/point-layout', { recursive: true })
  for (const width of [1536, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`${base}/#/axes/2`)
    await page.locator('.points-table input.point-name').waitFor()
    await page.locator('.points-table').scrollIntoViewIfNeeded()
    const metrics = await page.locator('.points-table').evaluate(table => {
      const row = table.tBodies[0].rows[0]
      const rect = el => { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height } }
      return { slot: rect(row.querySelector('strong')), name: rect(row.querySelector('.point-name')),
        cells: [...row.cells].map(rect), headers: [...table.tHead.rows[0].cells].map(rect),
        controls: [...row.querySelectorAll('input, .action-row button')].map(rect),
        claim: rect(table.closest('section').querySelector('select')),
        claimButton: rect(table.closest('section').querySelector(':scope > .action-row button')) }
    })
    const center = r => r.y + r.height / 2
    assert.ok(Math.abs(center(metrics.slot) - center(metrics.name)) < 2, `slot/name aligned at ${width}`)
    for (const control of metrics.controls) assert.ok(Math.abs(center(control) - center(metrics.name)) < 2, `controls aligned at ${width}`)
    for (let i = 0; i < metrics.cells.length; i++) assert.ok(Math.abs(metrics.cells[i].x - metrics.headers[i].x) < 1)
    assert.ok(metrics.name.x + metrics.name.width <= metrics.cells[0].x + metrics.cells[0].width - 8)
    assert.ok(Math.abs(center(metrics.claim) - center(metrics.claimButton)) < 2, 'claim controls aligned')
    await page.screenshot({ path: `validation/point-layout/${width}.png`, fullPage: true })
  }
  await page.setViewportSize({ width: 1536, height: 900 })
  await page.getByLabel('P2 位置', { exact: true }).fill('50.000')
  await page.getByLabel('P2 速度', { exact: true }).fill('5.000')
  await page.getByRole('button', { name: '写入', exact: true }).click()
  await page.waitForTimeout(200)
  assert.ok(writes.some(r => r.path === '/api/point' && r.body.position === 50 && r.body.speed === 5))
  await page.getByRole('button', { name: '示教', exact: true }).click()
  await page.waitForTimeout(200)
  assert.ok(writes.some(r => r.path === '/api/point' && r.body.position === 12.345))
  assert.ok(!writes.some(r => r.path === '/api/command'), 'point writes do not issue motion commands')
  assert.deepEqual(errors, [])
  console.log('Point layout passed at 1536/1024/390; manual write and current-position teach verified with mocked API only.')
} finally {
  await browser.close()
}
