import { useEffect, useRef } from 'react'

/**
 * Dot-matrix shield on a dark background.
 * Cheap to run: the dots are drawn once into two offscreen layers (dim, bright);
 * each frame only copies a moving bright band and a dozen red "attack" sparks that die on the shield edge.
 * Pauses when off screen. Static frame with reduced motion.
 */
export function ShieldField({ className = '', dark = true }: { className?: string; dark?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const reduce = typeof window.matchMedia !== 'function' || window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    let w = 1, h = 1, raf = 0, visible = true
    let dim: HTMLCanvasElement, bright: HTMLCanvasElement
    let shield = new Path2D()
    let cx = 0, cy = 0, R = 0
    type Spark = { a: number; r: number; v: number }
    let sparks: Spark[] = []

    function shieldPath(x: number, y: number, s: number) {
      const p = new Path2D()
      p.moveTo(x, y - s)
      p.bezierCurveTo(x + s * 0.55, y - s * 0.78, x + s * 0.82, y - s * 0.8, x + s * 0.86, y - s * 0.74)
      p.bezierCurveTo(x + s * 0.9, y + s * 0.05, x + s * 0.6, y + s * 0.7, x, y + s)
      p.bezierCurveTo(x - s * 0.6, y + s * 0.7, x - s * 0.9, y + s * 0.05, x - s * 0.86, y - s * 0.74)
      p.bezierCurveTo(x - s * 0.82, y - s * 0.8, x - s * 0.55, y - s * 0.78, x, y - s)
      return p
    }

    function layer(color: (inside: boolean, d: number) => string | null) {
      const c = document.createElement('canvas')
      c.width = w * dpr; c.height = h * dpr
      const g = c.getContext('2d')!
      g.scale(dpr, dpr)
      const step = w < 700 ? 11 : 13
      for (let y = step / 2; y < h; y += step) {
        for (let x = step / 2; x < w; x += step) {
          const inside = ctx!.isPointInPath(shield, x * dpr, y * dpr)
          const d = Math.hypot(x - cx, y - cy) / R
          const col = color(inside, d)
          if (!col) continue
          g.fillStyle = col
          const sz = inside ? 2.6 : 1.6
          g.fillRect(x - sz / 2, y - sz / 2, sz, sz)
        }
      }
      return c
    }

    function resize() {
      const r = canvas!.getBoundingClientRect()
      w = Math.max(1, r.width); h = Math.max(1, r.height)
      canvas!.width = w * dpr; canvas!.height = h * dpr
      cx = w < 900 ? w * 0.5 : w * 0.72
      cy = h * 0.5
      R = Math.min(h * 0.38, w < 900 ? w * 0.42 : w * 0.24)
      ctx!.setTransform(1, 0, 0, 1, 0, 0)
      shield = new Path2D()
      shield.addPath(shieldPath(cx * dpr, cy * dpr, R * dpr))
      dim = dark
        ? layer((inside, d) => inside ? `rgba(120,150,255,${0.28 - d * 0.1})` : d < 2.4 ? `rgba(110,125,170,${0.12 - d * 0.04})` : null)
        : layer((inside, d) => inside ? `rgba(39,71,224,${0.3 - d * 0.12})` : d < 2.4 ? `rgba(80,92,140,${0.14 - d * 0.05})` : null)
      bright = layer((inside) => inside ? (dark ? 'rgba(150,185,255,0.95)' : 'rgba(39,71,224,0.95)') : null)
      sparks = Array.from({ length: 14 }, () => ({ a: Math.random() * Math.PI * 2, r: 1.6 + Math.random() * 1.4, v: 0.18 + Math.random() * 0.25 }))
    }

    function frame(t: number) {
      ctx!.setTransform(1, 0, 0, 1, 0, 0)
      ctx!.clearRect(0, 0, canvas!.width, canvas!.height)
      ctx!.drawImage(dim, 0, 0)
      // bright scan band
      const band = 70 * dpr
      const y = ((t / 2600) % 1.3 - 0.15) * canvas!.height
      ctx!.save()
      ctx!.beginPath(); ctx!.rect(0, y - band / 2, canvas!.width, band); ctx!.clip()
      ctx!.drawImage(bright, 0, 0)
      ctx!.restore()
      // attack sparks: fly in, die on the shield edge
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      for (const s of sparks) {
        s.r -= s.v * 0.016
        const x = cx + Math.cos(s.a) * s.r * R
        const yy = cy + Math.sin(s.a) * s.r * R * 1.05
        if (s.r < 0.95) {
          // hit: small ring
          const k = (0.95 - s.r) / 0.15
          ctx!.strokeStyle = `rgba(229,72,107,${Math.max(0, 1 - k)})`
          ctx!.lineWidth = 1.5
          ctx!.beginPath(); ctx!.arc(x, yy, 4 + k * 14, 0, Math.PI * 2); ctx!.stroke()
          if (k >= 1) { s.r = 2.4 + Math.random(); s.a = Math.random() * Math.PI * 2 }
          continue
        }
        ctx!.fillStyle = dark ? 'rgba(240,90,125,0.95)' : 'rgba(229,72,107,0.95)'
        ctx!.fillRect(x - 2, yy - 2, 4, 4)
        ctx!.fillStyle = 'rgba(240,90,125,0.25)'
        ctx!.fillRect(x + Math.cos(s.a) * 8 - 1.5, yy + Math.sin(s.a) * 8 - 1.5, 3, 3)
      }
    }

    function loop(t: number) {
      if (visible) frame(t)
      raf = requestAnimationFrame(loop)
    }

    resize()
    if (reduce) frame(800); else raf = requestAnimationFrame(loop)
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => { resize(); if (reduce) frame(800) }) : null
    ro?.observe(canvas)
    const io = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(([e]) => { visible = e.isIntersecting }) : null
    io?.observe(canvas)
    return () => { cancelAnimationFrame(raf); ro?.disconnect(); io?.disconnect() }
  }, [dark])

  return <canvas ref={ref} aria-hidden className={className} />
}
