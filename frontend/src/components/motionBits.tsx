import { useEffect, useRef, type ReactNode } from 'react'
import { canAnimate, gsap, ScrollTrigger } from '../lib/motion'

/** Shows the final text at once; when scrolled into view it counts up from 0 to it. */
export function Counter({ value, format, className = '', testId }: { value: number; format: (n: number) => string; className?: string; testId?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const done = useRef(false)
  useEffect(() => {
    const el = ref.current
    if (!el || done.current || !canAnimate()) return
    const o = { n: 0 }
    const run = () => {
      if (done.current) return
      done.current = true
      gsap.to(o, { n: value, duration: 1.6, ease: 'power3.out', onUpdate: () => { el.textContent = format(o.n) }, onComplete: () => { el.textContent = format(value) } })
    }
    // Count up when it comes into view; if the page jumps past it, show the final number at once.
    const st = ScrollTrigger.create({
      trigger: el, start: 'top 88%', end: 'bottom top',
      onEnter: run, onEnterBack: run,
      onLeave: () => { if (!done.current) { done.current = true; el.textContent = format(value) } },
    })
    if (st.progress > 0 || st.isActive) run()
    el.textContent = format(0)
    return () => { st.kill(); if (!done.current) el.textContent = format(value) }
  }, [value, format])
  return <span ref={ref} data-testid={testId} className={className}>{format(value)}</span>
}

/** 3D tilt + glare following the mouse. */
export function Tilt({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  function move(e: React.MouseEvent) {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height
    el.style.setProperty('--ry', `${(x - 0.5) * 6}deg`)
    el.style.setProperty('--rx', `${(0.5 - y) * 6}deg`)
    el.style.setProperty('--gx', `${x * 100}%`)
    el.style.setProperty('--gy', `${y * 100}%`)
  }
  function leave() { ref.current?.style.setProperty('--rx', '0deg'); ref.current?.style.setProperty('--ry', '0deg') }
  return (
    <div ref={ref} onMouseMove={move} onMouseLeave={leave} className={`tilt relative overflow-hidden ${className}`}>
      {children}
      <div aria-hidden className="tilt-glare pointer-events-none absolute inset-0 mix-blend-soft-light" />
    </div>
  )
}

/** Button that leans toward the cursor. */
export function Magnetic({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  function move(e: React.MouseEvent) {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    gsap.to(el, { x: (e.clientX - r.left - r.width / 2) * 0.3, y: (e.clientY - r.top - r.height / 2) * 0.4, duration: 0.4, ease: 'power3.out' })
  }
  function leave() { if (ref.current) gsap.to(ref.current, { x: 0, y: 0, duration: 0.7, ease: 'elastic.out(1, 0.4)' }) }
  return <div ref={ref} onMouseMove={move} onMouseLeave={leave} className={`inline-block ${className}`}>{children}</div>
}
