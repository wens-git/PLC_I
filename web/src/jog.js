const uuid = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  // Plain-http LAN hosts are not secure contexts and lack crypto.randomUUID.
  const random = () => Math.floor(Math.random() * 0x100000000).toString(16).padStart(8, '0')
  return `${Date.now().toString(16)}-${random()}-${random()}-${random()}-${random()}`
}

export function createJog(post, getSession, { interval = 200, changed = () => {} } = {}) {
  let active = null
  let timer = null
  let renewing = false
  let generation = 0
  const clear = () => { clearInterval(timer); timer = null; changed(null) }
  const stop = async () => {
    generation++
    const lease = active
    active = null
    clear()
    if (lease) {
      await post('/api/jog/stop', { token: lease.token, session: lease.session }, { quiet: true, keepalive: true }).catch(() => {})
    }
  }
  const start = async (axis, direction) => {
    const stopping = stop()
    const request = generation
    await stopping
    if (request !== generation) return
    const lease = { axis, direction, token: uuid(), session: getSession() }
    active = lease
    changed(lease)
    // Proofs begin immediately: a queued start must not become a delayed motion.
    timer = setInterval(async () => {
      if (active !== lease || renewing) return
      renewing = true
      try { await post('/api/jog/renew', { token: lease.token, session: lease.session }, { quiet: true }) }
      catch { if (active === lease) await stop() }
      finally { renewing = false }
    }, interval)
    try {
      const result = await post('/api/jog/start', lease, { quiet: true })
      if (active !== lease) {
        await post('/api/jog/stop', { token: lease.token, session: lease.session }, { quiet: true, keepalive: true }).catch(() => {})
      } else if (result?.result) await stop()
    } catch { if (active === lease) await stop() }
  }
  return { start, stop, get active() { return active } }
}
