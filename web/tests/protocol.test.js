import { test } from 'node:test'
import assert from 'node:assert/strict'
import { scaled, validName } from '../src/protocol.js'

test('engineering inputs retain three-digit precision and DINT boundaries', () => {
  assert.equal(scaled('-2147483.648'), -2147483648)
  assert.equal(scaled('2147483.647', true), 2147483647)
  assert.equal(scaled('0.001', true), 1)
  assert.throws(() => scaled('1.0001'))
  assert.throws(() => scaled('2147483.648'))
  assert.throws(() => scaled('0', true))
  assert.throws(() => scaled('1e3'))
})
test('names are host metadata limited to 32 characters', () => {
  assert.equal(validName('1'.repeat(32)), '1'.repeat(32))
  assert.throws(() => validName('1'.repeat(33)))
  assert.equal(validName('  送料轴  '), '送料轴')
})
test('names reject control and replacement characters', () => {
  assert.equal(validName('轴名称'), '轴名称')
  assert.equal(validName('abcdefghijkl'), 'abcdefghijkl')
  assert.throws(() => validName('bad\0name'))
  assert.throws(() => validName('\uFFFD'))
  assert.throws(() => validName(''))
})
test('names reject lone surrogates but keep valid surrogate pairs', () => {
  const high = String.fromCharCode(0xD83D)
  const low = String.fromCharCode(0xDFFF)
  const pair = high + low
  assert.throws(() => validName('ab' + high + 'cd'))
  assert.throws(() => validName('ab' + low + 'cd'))
  assert.equal(validName(pair), pair)
  assert.equal(validName('设备' + pair + 'A'), '设备' + pair + 'A')
  assert.equal(validName(pair.repeat(32)), pair.repeat(32))
  assert.throws(() => validName(pair.repeat(33)))
})
