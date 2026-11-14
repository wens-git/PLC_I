import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createJog } from '../src/jog.js'

test('release before start ACK cancels lease and late ACK sends another stop', async () => {
  const calls = []
  let resolveStart
  const post = async (url, payload) => {
    calls.push({ url, payload })
    if (url.endsWith('/start')) return new Promise(resolve => { resolveStart = resolve })
    return { result: 0 }
  }
  const jog = createJog(post, () => 'session-one', { interval: 10 })
  const start = jog.start(2, -1)
  await new Promise(resolve => setTimeout(resolve, 25))
  await jog.stop()
  const count = calls.length
  await new Promise(resolve => setTimeout(resolve, 25))
  assert.equal(calls.length, count)
  resolveStart({ result: 0 })
  await start
  assert.equal(calls.filter(c => c.url.endsWith('/stop')).length, 2)
  assert.equal(jog.active, null)
  assert.equal(new Set(calls.map(c => c.payload.token)).size, 1)
  assert.ok(calls.every(c => c.payload.session === 'session-one'))
})
test('renewal failure ends lease', async () => {
  const calls = []
  const post = async url => {
    calls.push(url)
    if (url.endsWith('/renew')) throw new Error('offline')
    return { result: 0 }
  }
  const jog = createJog(post, () => 's', { interval: 5 })
  await jog.start(0, 1)
  await new Promise(resolve => setTimeout(resolve, 20))
  assert.equal(jog.active, null)
  assert.ok(calls.includes('/api/jog/stop'))
})
test('release while waiting for previous stop prevents a new start', async () => {
  const calls = []
  let resolveStop
  const post = async url => {
    calls.push(url)
    if (url.endsWith('/stop')) return new Promise(resolve => { resolveStop = resolve })
    return { result: 0 }
  }
  const jog = createJog(post, () => 's')
  await jog.start(0, 1)
  const second = jog.start(0, -1)
  await jog.stop()
  resolveStop({ result: 0 })
  await second
  assert.equal(calls.filter(url => url.endsWith('/start')).length, 1)
  assert.equal(jog.active, null)
})
