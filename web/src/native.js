// QWebChannel owns both requests and the state stream in the desktop application.
export function createNativeClient(bridge, { timeout = 13000 } = {}) {
  let serial = 0, closed = false
  const pending = new Map(), subscribers = new Set(), suspendListeners = new Set()
  const response = raw => {
    let packet
    try { packet = JSON.parse(raw) } catch { return }
    const entry = pending.get(packet.id)
    if (!entry) return
    pending.delete(packet.id); clearTimeout(entry.timer)
    entry.resolve({ status: packet.status, body: packet.body })
  }
  const snapshot = raw => {
    try { const state = JSON.parse(raw); for (const listener of subscribers) listener(state) } catch { /* freshness watchdog handles invalid snapshots */ }
  }
  const suspended = () => { for (const listener of suspendListeners) listener() }
  bridge.response.connect(response)
  bridge.snapshot.connect(snapshot)
  bridge.suspended.connect(suspended)
  return {
    request(method, path, payload = {}) {
      if (closed) return Promise.reject(new Error('桌面桥接已关闭'))
      const id = String(++serial)
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => { pending.delete(id); reject(new Error('请求超时，结果未知；请核查设备状态')) }, timeout)
        pending.set(id, { resolve, reject, timer })
        try { bridge.request(JSON.stringify({ id, method, path, payload })) }
        catch (error) { clearTimeout(timer); pending.delete(id); reject(error) }
      })
    },
    subscribe(listener) { subscribers.add(listener); return () => subscribers.delete(listener) },
    onSuspend(listener) { suspendListeners.add(listener); return () => suspendListeners.delete(listener) },
    close() {
      closed = true
      bridge.response.disconnect(response); bridge.snapshot.disconnect(snapshot); bridge.suspended.disconnect(suspended)
      for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(new Error('桌面桥接已关闭，结果未知')) }
      pending.clear(); subscribers.clear(); suspendListeners.clear()
    },
  }
}

let nativePromise
export const isNative = () => typeof window !== 'undefined' && Boolean(window.qt?.webChannelTransport)
export async function getNativeClient() {
  if (!isNative()) return null
  if (!nativePromise) nativePromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'qrc:///qtwebchannel/qwebchannel.js'
    script.onerror = () => reject(new Error('桌面通信组件加载失败'))
    script.onload = () => {
      const timer = setTimeout(() => reject(new Error('桌面通信初始化超时')), 5000)
      new window.QWebChannel(window.qt.webChannelTransport, channel => {
        clearTimeout(timer); resolve(createNativeClient(channel.objects.hmi))
      })
    }
    document.head.appendChild(script)
  })
  return nativePromise
}
