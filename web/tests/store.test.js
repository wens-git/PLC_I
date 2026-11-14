import { test } from 'node:test'
import assert from 'node:assert/strict'
import { hmi, post } from '../src/store.js'

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})

test('expired csrf token refreshes meta and retries once', async () => {
  const tokens = []
  globalThis.fetch = async (url, init = {}) => {
    if (url === '/api/meta') return json({ version: 't', csrf_token: 'fresh', rejections: {} })
    tokens.push(init.headers['X-CSRF-Token'])
    if (tokens.length === 1) return json({ detail: '请求令牌无效' }, 403)
    return json({ result: 0, message: '已受理' })
  }
  hmi.meta = { csrf_token: 'stale', rejections: {} }
  const body = await post('/api/command', { code: 1 })
  assert.equal(body.message, '已受理')
  assert.deepEqual(tokens, ['stale', 'fresh'])
  assert.equal(hmi.meta.csrf_token, 'fresh')
})

test('csrf retry never loops', async () => {
  const posts = []
  globalThis.fetch = async (url, init = {}) => {
    if (url === '/api/meta') return json({ csrf_token: 'fresh', rejections: {} })
    posts.push(init.headers['X-CSRF-Token'])
    return json({ detail: '请求令牌无效' }, 403)
  }
  hmi.meta = { csrf_token: 'stale', rejections: {} }
  await assert.rejects(post('/api/command', { code: 1 }), /请求令牌无效/)
  assert.equal(posts.length, 2)
})

test('non-json responses surface a friendly error', async () => {
  globalThis.fetch = async () => new Response('<html>gateway timeout</html>', { status: 504 })
  hmi.meta = { csrf_token: 't', rejections: {} }
  hmi.toasts = []
  await assert.rejects(post('/api/command', { code: 1 }), /服务响应异常/)
  assert.ok(hmi.toasts.some(t => t.message.includes('服务响应异常')))
})

test('missing csrf meta failure is not silent', async () => {
  globalThis.fetch = async url => {
    if (url === '/api/meta') throw new TypeError('network down')
    throw new Error('unexpected fetch')
  }
  hmi.meta = { csrf_token: '', rejections: {} }
  hmi.toasts = []
  await assert.rejects(post('/api/command', { code: 1 }), /network down/)
  assert.ok(hmi.toasts.some(t => t.message.includes('network down')))
})

test('error and message fields surface without a detail string', async () => {
  hmi.meta = { csrf_token: 't', rejections: {} }
  hmi.toasts = []
  globalThis.fetch = async () => json({ error: '前端资源未生成' }, 503)
  await assert.rejects(post('/api/command', { code: 1 }), /前端资源未生成/)
  globalThis.fetch = async () => json({ message: '服务维护中' }, 503)
  await assert.rejects(post('/api/command', { code: 1 }), /服务维护中/)
})
