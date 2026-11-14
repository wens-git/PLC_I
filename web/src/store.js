import { computed, reactive } from 'vue'
import { createJog } from './jog.js'
import { getNativeClient, isNative } from './native.js'

export const hmi = reactive({
  state: { connected: false, handshake: false, mode: 'offline', axes: [], cylinders: [], io: { x: [], y: [] }, events: [], global_permit: 0 },
  meta: { csrf_token: '', rejections: {} }, stream: false, lastSnapshot: 0, pending: {}, toasts: [], history: [], jog: null,
})
export const ready = computed(() => hmi.stream && hmi.state.connected && hmi.state.handshake)
let socket, reconnect, watchdog, stopped = false, connections = 0
let unsubscribeNative, unsubscribeSuspend
let toastId = 0
const toastTimers = new Map()
export function reason(code) {
  if (!Number(code)) return '按 PLC 许可执行'
  const entries = hmi.meta.rejections
  const entry = Array.isArray(entries) ? entries.find(item => item.code === Number(code)) : entries?.[code]
  return typeof entry === 'string' ? entry : entry?.message || (Number(code) ? `闭锁原因 ${code}` : '按 PLC 许可执行')
}
export function notify(message, good = false, detail = '') {
  const item = { id: ++toastId, message, good, detail, time: new Date().toISOString(), source: 'browser' }
  hmi.toasts.unshift(item)
  hmi.history.unshift(item)
  hmi.history.splice(200)
  const timer = setTimeout(() => {
    toastTimers.delete(item.id)
    hmi.toasts = hmi.toasts.filter(t => t.id !== item.id)
  }, 4000)
  toastTimers.set(item.id, timer)
}
export async function loadMeta() {
  if (isNative()) {
    hmi.meta = await nativeRequest('GET', '/api/meta')
    return
  }
  const response = await fetch('/api/meta', { cache: 'no-store' })
  if (!response.ok) throw new Error(`服务不可用 (${response.status})`)
  hmi.meta = await response.json()
}
async function readBody(response) {
  try { return await response.json() } catch { return {} }
}
async function nativeRequest(method, path, payload = {}) {
  const client = await getNativeClient()
  const { status, body } = await client.request(method, path, payload)
  if (status < 200 || status >= 300) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body))
  return body
}
async function currentState(signal) {
  if (isNative()) return nativeRequest('GET', '/api/state')
  return (await fetch('/api/state', { cache: 'no-store', signal })).json()
}
export async function post(path, payload = {}, options = {}) {
  const controller = new AbortController()
  // The backend waits 12s for its own ACK and answers 504 first; stay behind it.
  const timeout = setTimeout(() => controller.abort(), 13000)
  const send = () => fetch(path, {
    method: options.method || 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': hmi.meta.csrf_token },
    body: JSON.stringify(payload), keepalive: Boolean(options.keepalive), signal: controller.signal,
  })
  try {
    let body
    if (isNative()) {
      body = await nativeRequest(options.method || 'POST', path, payload)
    } else {
      if (!hmi.meta.csrf_token) await loadMeta()
      let response = await send()
      body = await readBody(response)
      if (response.status === 403 && typeof body.detail === 'string' && body.detail.includes('令牌')) {
        // A backend restart rotates the CSRF token; refresh once and replay.
        await loadMeta()
        response = await send()
        body = await readBody(response)
      }
      if (!response.ok) {
        throw new Error(typeof body.detail === 'string' ? body.detail
          : body.error || body.message || (body.detail ? JSON.stringify(body.detail) : `服务响应异常，请检查后端 (${response.status})`))
      }
    }
    if ('result' in body && body.result !== 0) throw new Error(`${body.message || reason(body.result)} · 拒绝码 ${body.result}`)
    if (['/api/config', '/api/name', '/api/point'].includes(path) || path.startsWith('/api/point/')) {
      // Publish the new epoch before clearing pending; the stream can lag an ACK.
      const readback = body.readback || await currentState(controller.signal)
      if (readback.session === payload.session && hmi.state.session === payload.session) accept(readback)
    }
    if (!options.quiet) notify(options.success || body.message || ('result' in body ? '已受理' : '请求完成'), true, body.seq ? `SEQ ${body.seq} · 已受理不代表动作完成` : '')
    return body
  } catch (error) {
    const message = error.name === 'AbortError' ? '请求超时，结果未知；请核查设备状态' : error.message || '网络异常，结果未知'
    if (!options.quiet) notify(message)
    throw error
  } finally { clearTimeout(timeout) }
}
export async function run(key, path, payload, options) {
  if (hmi.pending[key]) return false
  hmi.pending[key] = true
  try { await post(path, payload, options); return true }
  catch { return false }
  finally { delete hmi.pending[key] }
}
export function saveName(object_type, object_index, name, revision = hmi.state.names_revision) {
  // Host-only metadata: no PLC command, no config epoch. Pass the revision seen when
  // the edit began so a concurrent change by another terminal is reported, not overwritten.
  const payload = { object_type, object_index, revision: revision ?? null, session: hmi.state.session }
  if (name == null) return run(`name:${object_type}:${object_index}`, '/api/name', payload, { method: 'DELETE', success: '名称已恢复默认' })
  return run(`name:${object_type}:${object_index}`, '/api/name', { ...payload, name }, { success: '名称已保存（仅上位机）' })
}
export function command(code, object_type = 0, object_index = 0, a = 0, b = 0, c = 0) {
  return run(`command:${code}:${object_type}:${object_index}`, '/api/command', { code, object_type, object_index, a, b, c, staging: [], session: hmi.state.session })
}
export const jog = createJog(post, () => hmi.state.session, { changed: lease => { hmi.jog = lease } })
function accept(state) {
  if (hmi.state.session !== state.session || !state.connected || !state.handshake) jog.stop()
  hmi.state = state
  hmi.lastSnapshot = Date.now()
}
function openSocket() {
  if (stopped) return
  // A late onclose from a previous connection must not schedule a second stream.
  const generation = ++connections
  socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
  socket.onmessage = event => {
    try {
      const message = JSON.parse(event.data)
      if (message.type === 'snapshot' && message.state) { hmi.stream = true; accept(message.state) }
    } catch { /* Ignore incomplete messages; the freshness watchdog closes stale streams. */ }
  }
  socket.onclose = () => {
    hmi.stream = false
    jog.stop()
    if (generation === connections && !stopped) reconnect = setTimeout(openSocket, 1000)
  }
  socket.onerror = () => socket.close()
}
const stopJog = () => { jog.stop() }
const visibility = () => { if (document.hidden) jog.stop() }
export async function start() {
  stopped = false
  const generation = ++connections
  try {
    await loadMeta()
    if (stopped || generation !== connections) return
    accept(await currentState())
    if (stopped || generation !== connections) return
  } catch (error) { notify(error.message) }
  if (isNative()) {
    const client = await getNativeClient()
    if (stopped || generation !== connections) return
    unsubscribeNative = client.subscribe(state => { hmi.stream = true; accept(state) })
    unsubscribeSuspend = client.onSuspend(stopJog)
  } else openSocket()
  watchdog = setInterval(() => {
    if (hmi.stream && Date.now() - hmi.lastSnapshot > 1500) { hmi.stream = false; jog.stop(); socket?.close() }
  }, 250)
  window.addEventListener('blur', stopJog)
  window.addEventListener('pointerup', stopJog)
  window.addEventListener('pointercancel', stopJog)
  window.addEventListener('pagehide', stopJog)
  document.addEventListener('visibilitychange', visibility)
}
export function shutdown() {
  stopped = true
  connections++
  jog.stop(); socket?.close(); clearTimeout(reconnect); clearInterval(watchdog)
  unsubscribeNative?.(); unsubscribeSuspend?.(); unsubscribeNative = unsubscribeSuspend = null
  for (const timer of toastTimers.values()) clearTimeout(timer)
  toastTimers.clear()
  window.removeEventListener('blur', stopJog)
  window.removeEventListener('pointerup', stopJog)
  window.removeEventListener('pointercancel', stopJog)
  window.removeEventListener('pagehide', stopJog)
  document.removeEventListener('visibilitychange', visibility)
}
