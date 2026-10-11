import { act, renderHook } from '@testing-library/react'
import { usePolling } from './usePolling'

describe('usePolling (T6-04)', () => {
  beforeEach(() => { vi.useFakeTimers() })

  it('calls immediately then every 2s', async () => {
    const f = vi.fn().mockResolvedValue(1)
    renderHook(() => usePolling(f, 2000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    expect(f).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
    expect(f).toHaveBeenCalledTimes(3)
  })

  it('never overlaps', async () => {
    const f = vi.fn(() => new Promise<number>(() => {}))
    renderHook(() => usePolling(f, 2000))
    await act(async () => { await vi.advanceTimersByTimeAsync(10000) })
    expect(f).toHaveBeenCalledTimes(1)
  })

  it('keeps data on error', async () => {
    const f = vi.fn().mockResolvedValueOnce({ a: 1 }).mockRejectedValue(new Error('down'))
    const { result } = renderHook(() => usePolling(f, 2000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(result.current.data).toEqual({ a: 1 })
    expect(result.current.error?.message).toBe('down')
  })

  it('stops on unmount', async () => {
    const f = vi.fn().mockResolvedValue(1)
    const { unmount } = renderHook(() => usePolling(f, 2000))
    await act(async () => { await vi.advanceTimersByTimeAsync(0) })
    unmount()
    f.mockClear()
    await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
    expect(f).toHaveBeenCalledTimes(0)
  })
})
