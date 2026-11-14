import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { rmSync, writeFileSync } from 'node:fs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(root, '..')
let backend, vite, backendPort, vitePort

const freePort = () => new Promise(resolve => {
  const server = net.createServer()
  server.listen(0, '127.0.0.1', () => { const { port } = server.address(); server.close(() => resolve(port)) })
})

const waitFor = async (port, pathname, tries = 100) => {
  for (let i = 0; i < tries; i++) {
    try {
      const status = await raw(port, `GET ${pathname} HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\nConnection: close\r\n\r\n`, false)
      if (status) return
    } catch { /* not ready */ }
    await new Promise(r => setTimeout(r, 150))
  }
  throw new Error(`server on ${port} did not become ready`)
}

function raw(port, payload, keepAlive = true, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const socket = net.connect(port, '127.0.0.1')
    let data = ''
    socket.setTimeout(timeoutMs, () => { socket.destroy(); reject(new Error('timeout')) })
    socket.on('connect', () => socket.write(payload))
    socket.on('data', chunk => { data += chunk.toString(); if (!keepAlive) { socket.end() } })
    socket.on('end', () => { resolve(data); socket.destroy() })
    socket.on('error', reject)
  })
}

const statusLine = data => data.split('\r\n', 1)[0]

before(async () => {
  backendPort = await freePort()
  vitePort = await freePort()
  backend = spawn('python', ['launcher.py', '--port', String(backendPort), '--no-browser'], { cwd: repo, stdio: 'ignore' })
  vite = spawn(process.execPath, [path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(vitePort), '--strictPort'], {
    cwd: root, stdio: 'ignore', env: { ...process.env, VITE_API_TARGET: `http://127.0.0.1:${backendPort}` },
  })
  await waitFor(backendPort, '/api/meta')
  await waitFor(vitePort, '/api/meta')
})

after(() => {
  for (const child of [vite, backend]) {
    if (child && child.exitCode === null) child.kill()
  }
})

test('dev server survives file churn in tests directory', async () => {
  const churn = path.join(root, 'tests', '_churn.tmp')
  writeFileSync(churn, 'x')
  await new Promise(r => setTimeout(r, 300))
  rmSync(churn)
  await new Promise(r => setTimeout(r, 300))
  const meta = await raw(vitePort, `GET /api/meta HTTP/1.1\r\nHost: 127.0.0.1:${vitePort}\r\nConnection: close\r\n\r\n`, false)
  assert.match(statusLine(meta), /200/, 'dev server died from watcher churn')
})

test('dev proxy keeps origin/host consistent so backend accepts API writes', async () => {
  const metaPath = `/api/meta`
  const metaHost = `127.0.0.1:${vitePort}`
  const getMeta = await raw(vitePort, `GET ${metaPath} HTTP/1.1\r\nHost: ${metaHost}\r\nConnection: close\r\n\r\n`, false)
  assert.match(statusLine(getMeta), /200/)
  const token = JSON.parse(getMeta.split('\r\n\r\n')[1]).csrf_token

  const origin = `http://127.0.0.1:${vitePort}`
  const post = await raw(vitePort, [
    `POST /api/disconnect HTTP/1.1`,
    `Host: ${metaHost}`,
    `Origin: ${origin}`,
    `X-CSRF-Token: ${token}`,
    `Content-Type: application/json`,
    `Content-Length: 2`,
    `Connection: close`,
    ``,
    `{}`,
  ].join('\r\n'), false)
  assert.doesNotMatch(statusLine(post), /403/, `proxy write rejected: ${statusLine(post)}`)
  assert.match(statusLine(post), /200/)
})

test('dev proxy forwards websocket upgrade with consistent origin', async () => {
  const host = `127.0.0.1:${vitePort}`
  const payload = [
    `GET /ws HTTP/1.1`,
    `Host: ${host}`,
    `Upgrade: websocket`,
    `Connection: Upgrade`,
    `Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==`,
    `Sec-WebSocket-Version: 13`,
    `Origin: http://${host}`,
    ``,
    ``,
  ].join('\r\n')
  const data = await new Promise((resolve, reject) => {
    const socket = net.connect(vitePort, '127.0.0.1')
    let collected = ''
    const timer = setTimeout(() => { socket.destroy(); resolve(collected) }, 600)
    socket.on('connect', () => socket.write(payload))
    socket.on('data', chunk => { collected += chunk.toString() })
    socket.on('error', error => { clearTimeout(timer); reject(error) })
  })
  assert.match(statusLine(data), /101/, `websocket rejected: ${statusLine(data)}`)
  assert.ok(data.includes('"type":"snapshot"'), `no backend snapshot frame, got: ${data.slice(-200)}`)
})
