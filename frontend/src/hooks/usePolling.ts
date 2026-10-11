import { useCallback, useEffect, useRef, useState } from 'react'

export interface Polled<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  lastUpdated: number | undefined
  refresh: () => Promise<void>
}

/** Calls fetcher now, then again intervalMs after each call finishes. Never two requests in flight. */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 2000, deps: unknown[] = []): Polled<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<number>()
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const inFlight = useRef(false)
  const cancelled = useRef(false)

  const tick = useCallback(async () => {
    if (inFlight.current || cancelled.current) return
    inFlight.current = true
    clearTimeout(timer.current)
    try {
      const v = await fetcherRef.current()
      if (cancelled.current) return
      setData(v)
      setError(undefined)
      setLastUpdated(Date.now())
    } catch (e) {
      if (cancelled.current) return
      setError(e instanceof Error ? e : new Error(String(e)))
    } finally {
      inFlight.current = false
      if (!cancelled.current) {
        setLoading(false)
        timer.current = setTimeout(() => { void tick() }, intervalMs)
      }
    }
  }, [intervalMs])

  useEffect(() => {
    cancelled.current = false
    void tick()
    return () => { cancelled.current = true; clearTimeout(timer.current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick, ...deps])

  return { data, error, loading, lastUpdated, refresh: tick }
}
