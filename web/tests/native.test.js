import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createNativeClient } from '../src/native.js'

function signal() {
  const listeners = new Set()
  return { connect: fn => listeners.add(fn), disconnect: fn => listeners.delete(fn), emit: value => { for (const fn of listeners) fn(value) } }
}
function fixture() {
  const sent = []
  const bridge = { response: signal(), snapshot: signal(), suspended: signal(), request: value => sent.push(JSON.parse(value)) }
  return { bridge, sent, client: createNativeClient(bridge, { timeout: 30 }) }
}
test('native requests correlate out-of-order replies and preserve refusal details', async () => {
  const { bridge, sent, client } = fixture()
  const a = client.request('POST', '/api/command', { code: 20 })
  const b = client.request('GET', '/api/state')
  bridge.response.emit(JSON.stringify({ id: sent[1].id, status: 200, body: { session: 's' } }))
  bridge.response.emit(JSON.stringify({ id: sent[0].id, status: 409, body: { detail: '会话已变化' } }))
  assert.deepEqual((await b).body, { session: 's' })
  assert.equal((await a).status, 409)
  assert.equal(sent[0].payload.code, 20)
  client.close()
})
test('bridge timeout never retries an action and ignores late replies', async () => {
  const { bridge, sent, client } = fixture()
  await assert.rejects(client.request('POST', '/api/command', { code: 2 }), /结果未知/)
  assert.equal(sent.length, 1)
  bridge.response.emit(JSON.stringify({ id: sent[0].id, status: 200, body: {} }))
  client.close()
})
test('native stream delivers snapshots and close rejects outstanding requests', async () => {
  const { bridge, client } = fixture()
  const states = []
  const unsubscribe = client.subscribe(state => states.push(state))
  bridge.snapshot.emit(JSON.stringify({ session: 's' }))
  assert.deepEqual(states, [{ session: 's' }])
  unsubscribe()
  bridge.snapshot.emit(JSON.stringify({ session: 'later' }))
  assert.equal(states.length, 1)
  const request = client.request('POST', '/api/jog/start', {})
  client.close()
  await assert.rejects(request, /桥接已关闭/)
})
