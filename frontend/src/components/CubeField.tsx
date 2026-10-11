import { useEffect, useRef } from 'react'

/**
 * Isometric cubes drift right toward a vertical "guard" line.
 * Blue cubes (normal operations) pass and become data bars; rose cubes (attack) stop at the line and fade.
 * Static frame when the user prefers reduced motion.
 */
interface Cube { x: number; y: number; s: number; v: number; bad: boolean; life: number; hue: number }

export function CubeField({ className = '' }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 0, h = 0, raf = 0, last = 0
    let cubes: Cube[] = []
    let bars: { y: number; x: number; len: number; a: number }[] = []

    const gx = () => w * 0.62 // guard line x
    const start = () => (w < 900 ? w * 0.05 : w * 0.4) // cubes are born here, right of the headline

    function spawn(initial = false): Cube {
      const bad = Math.random() < 0.18
      return {
        x: initial ? start() + Math.random() * (gx() - start()) : start() - Math.random() * 30,
        y: h * 0.12 + Math.random() * h * 0.8,
        s: 5 + Math.random() * 11,
        v: 18 + Math.random() * 30,
        bad, life: 1, hue: Math.random(),
      }
    }

    function resize() {
      const r = canvas!.getBoundingClientRect()
      w = Math.max(1, r.width); h = Math.max(1, r.height)
      canvas!.width = w * dpr; canvas!.height = h * dpr
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      const n = Math.round(Math.min(110, (w * h) / 5200))
      cubes = Array.from({ length: n }, () => spawn(true))
      bars = Array.from({ length: 26 }, (_, i) => ({ y: h * 0.42 + i * (h * 0.5 / 26), x: gx() + 20 + Math.random() * 60, len: 40 + Math.random() * (w * 0.3), a: 0.25 + Math.random() * 0.6 }))
    }

    function cube(x: number, y: number, s: number, bad: boolean, hue: number, alpha: number) {
      const top = bad ? `rgba(240,120,150,${alpha})` : `rgba(${150 + hue * 60},${175 + hue * 40},255,${alpha})`
      const left = bad ? `rgba(214,62,98,${alpha})` : `rgba(${70 + hue * 40},${100 + hue * 40},230,${alpha})`
      const right = bad ? `rgba(170,40,75,${alpha})` : `rgba(${40 + hue * 30},${62 + hue * 30},190,${alpha})`
      const c = s * 0.866, d = s * 0.5
      ctx!.fillStyle = top
      ctx!.beginPath(); ctx!.moveTo(x, y - s); ctx!.lineTo(x + c, y - d); ctx!.lineTo(x, y); ctx!.lineTo(x - c, y - d); ctx!.closePath(); ctx!.fill()
      ctx!.fillStyle = left
      ctx!.beginPath(); ctx!.moveTo(x - c, y - d); ctx!.lineTo(x, y); ctx!.lineTo(x, y + s); ctx!.lineTo(x - c, y + d); ctx!.closePath(); ctx!.fill()
      ctx!.fillStyle = right
      ctx!.beginPath(); ctx!.moveTo(x + c, y - d); ctx!.lineTo(x, y); ctx!.lineTo(x, y + s); ctx!.lineTo(x + c, y + d); ctx!.closePath(); ctx!.fill()
    }

    function draw(t: number) {
      const dt = last ? Math.min(0.05, (t - last) / 1000) : 0
      last = t
      ctx!.clearRect(0, 0, w, h)
      const g = gx()
      // data bars to the right of the guard
      for (const b of bars) {
        const shimmer = reduce ? 0 : Math.sin(t / 1400 + b.y) * 12
        const grad = ctx!.createLinearGradient(b.x, 0, b.x + b.len, 0)
        grad.addColorStop(0, `rgba(39,71,224,${b.a})`)
        grad.addColorStop(1, `rgba(79,123,255,${b.a * 0.4})`)
        ctx!.fillStyle = grad
        ctx!.fillRect(b.x + shimmer, b.y, b.len, 5)
      }
      // guard line
      const lg = ctx!.createLinearGradient(0, 0, 0, h)
      lg.addColorStop(0, 'rgba(14,127,168,0)'); lg.addColorStop(0.25, 'rgba(14,127,168,0.7)'); lg.addColorStop(1, 'rgba(14,127,168,0.15)')
      ctx!.fillStyle = lg
      ctx!.fillRect(g - 1.5, h * 0.05, 3, h * 0.95)
      ctx!.fillStyle = 'rgba(79,180,220,0.12)'
      ctx!.fillRect(g - 10, h * 0.05, 20, h * 0.95)
      // cubes
      for (let i = 0; i < cubes.length; i++) {
        const q = cubes[i]
        if (q.bad && q.x >= g - q.s * 1.2) {
          q.x = g - q.s * 1.2
          q.life -= dt * 0.9
        } else {
          q.x += q.v * dt
        }
        if (!q.bad && q.x > g) q.life -= dt * 2.5
        if (q.life <= 0 || q.x > w + 20) { cubes[i] = spawn(); continue }
        const fadeIn = Math.max(0, Math.min(1, (q.x - start()) / 70))
        cube(q.x, q.y, q.s, q.bad, q.hue, Math.max(0, Math.min(1, q.life)) * 0.9 * fadeIn)
      }
      if (!reduce) raf = requestAnimationFrame(draw)
    }

    resize()
    if (reduce) draw(0); else raf = requestAnimationFrame(draw)
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => { resize(); if (reduce) draw(0) }) : null
    ro?.observe(canvas)
    return () => { cancelAnimationFrame(raf); ro?.disconnect() }
  }, [])

  return <canvas ref={ref} aria-hidden className={className} />
}
