import { api, ApiError, isNoSnapshotYet } from './api'
import stateFixture from '@fixtures/state.json'

const json = (x: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(x), { status }))

describe('api client (T6-05)', () => {
  it('fixture mode never calls fetch', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true')
    const f = vi.fn(); vi.stubGlobal('fetch', f)
    const s = await api.state()
    expect(s.block_number).toBe(stateFixture.block_number)
    expect(f).not.toHaveBeenCalled()
  })
  it('series url', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    const f = vi.fn(() => json([])); vi.stubGlobal('fetch', f)
    await api.series('lend-eth', 'WETH', 300)
    expect(f).toHaveBeenCalledWith('http://localhost:8000/api/series?deployment_id=lend-eth&asset=WETH&limit=300', undefined)
  })
  it('404 raises ApiError', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'decision not found' }, 404)))
    await expect(api.verify('X')).rejects.toMatchObject({ status: 404, detail: 'decision not found' })
  })
  it('fixture series key', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true')
    expect((await api.series('lend-eth', 'WETH')).length).toBe(41)
  })
  it('503 = no snapshot yet', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    vi.stubGlobal('fetch', vi.fn(() => json({ detail: 'no snapshot yet' }, 503)))
    const err = await api.state().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(isNoSnapshotYet(err)).toBe(true)
  })
  it('demo attack body', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    const f = vi.fn((_u: string, _i?: RequestInit) => json({})); vi.stubGlobal('fetch', f)
    await api.demoAttack(7, 'slow')
    expect(f.mock.calls[0][1]?.body).toBe('{"seed":7,"variant":"slow"}')
  })
})
