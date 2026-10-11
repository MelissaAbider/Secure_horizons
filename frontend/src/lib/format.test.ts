import {
  formatBpsPct, formatCountdown, formatPct, formatRate, formatTtd, formatUnits, formatUsd, shortHash, utilizationTone, withdrawableTone,
} from './format'

describe('format (T6-03)', () => {
  it('usd', () => {
    expect(formatUsd(1325000)).toBe('$1,325,000')
    expect(formatUsd(0)).toBe('$0')
  })
  it('units with BigInt', () => {
    expect(formatUnits('1850000000000000000000', 18)).toBe('1,850')
    expect(formatUnits('400000000000', 6)).toBe('400,000')
    expect(formatUnits('1500000000000000000', 18)).toBe('1.5')
    expect(formatUnits('0', 18)).toBe('0')
  })
  it('bps', () => {
    expect(formatBpsPct(1935)).toBe('19.4%')
    expect(formatBpsPct(10000)).toBe('100.0%')
    expect(formatBpsPct(6714)).toBe('67.1%')
  })
  it('tones', () => {
    expect(withdrawableTone(8000)).toBe('ok')
    expect(withdrawableTone(7999)).toBe('warn')
    expect(withdrawableTone(5000)).toBe('warn')
    expect(withdrawableTone(4999)).toBe('bad')
    expect(utilizationTone(9800)).toBe('bad')
  })
  it('hash, countdown, metrics', () => {
    expect(shortHash('0x433c5ce05750d9c9189b632954beb23cccdbf172c5556778a026ccf10a6f74cc')).toBe('0x433c…74cc')
    expect(formatCountdown('2026-10-11T12:02:27Z', Date.parse('2026-10-11T08:02:27Z'))).toBe('4 h 00 min left')
    expect(formatCountdown('2026-10-11T07:00:00Z', Date.parse('2026-10-11T08:05:00Z'))).toBe('overdue by 1 h 05 min')
    expect(formatRate(0.95)).toBe('95.0%')
    expect(formatRate(0)).toBe('0.0%')
    expect(formatPct(87.5)).toBe('87.5%')
    expect(formatTtd(-1)).toBe('not detected')
    expect(formatTtd(1)).toBe('1 block')
    expect(formatTtd(3)).toBe('3 blocks')
  })
})
