// Scroll motion: GSAP ScrollTrigger driven by Lenis smooth scrolling.
// Everything is opt-in: in tests (jsdom) or with "reduce motion", nothing animates and all content stays visible.
import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import Lenis from 'lenis'

gsap.registerPlugin(ScrollTrigger)

export { gsap, ScrollTrigger }

export function canAnimate(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  if (navigator.userAgent.includes('jsdom')) return false
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

let lenis: Lenis | null = null

/** Start smooth scrolling once for the whole app. Returns a stop function. */
export function startSmoothScroll(): () => void {
  if (!canAnimate() || lenis) return () => {}
  const l = new Lenis({ duration: 1.15, smoothWheel: true, wheelMultiplier: 0.95 })
  lenis = l
  l.on('scroll', ScrollTrigger.update)
  const tick = (t: number) => l.raf(t * 1000)
  gsap.ticker.add(tick)
  gsap.ticker.lagSmoothing(0)
  return () => { gsap.ticker.remove(tick); l.destroy(); lenis = null }
}

export function scrollToId(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  if (lenis) lenis.scrollTo(el, { offset: -20 })
  else el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
