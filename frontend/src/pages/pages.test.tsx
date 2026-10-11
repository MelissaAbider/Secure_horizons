import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from '../App'
import stateFixture from '@fixtures/state.json'
import { OverviewView } from './Overview'
import type { StateResponse } from '../types'

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>)
const json = (x: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(x), { status }))

describe('Overview (T6-06, T6-07, T6-08)', () => {
  it('renders the fixture story', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true')
    renderAt('/')
    expect(await screen.findByTestId('total-value')).toHaveTextContent('$1,325,000')
    expect(screen.getByTestId('risk-badge')).toHaveTextContent('CRITICAL')
    expect(screen.getByTestId('vault-status')).toHaveTextContent('PAUSED')
    expect(screen.getByTestId('backing-card')).toHaveTextContent('19.4%')
    expect(screen.getAllByTestId('reserve-row')).toHaveLength(6)
    const open = stateFixture.positions.filter((p: { supplied: string }) => p.supplied !== '0').length
    expect(screen.queryAllByTestId('position-row')).toHaveLength(open)
  })
  it('no positions message and waiting state', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    vi.stubGlobal('fetch', vi.fn((u: string) => u.includes('/api/state') ? json({ detail: 'no snapshot yet' }, 503) : json([])))
    renderAt('/')
    expect(await screen.findByTestId('waiting-first-block')).toHaveTextContent('Waiting for first block')
    expect(screen.queryByTestId('total-value')).toBeNull()
    expect(screen.queryByText(/Backend unreachable/)).toBeNull()
  })
  it('withdrawable bar tones', () => {
    const s = structuredClone(stateFixture) as unknown as StateResponse
    const base = { wallet: '0x', deployment_id: 'lend-eth', supplied: '1000000', withdrawable_now: '1', value_usd: 1, withdrawable_usd: 1 }
    s.positions = [10000, 7000, 4000].map((b, i) => ({ ...base, asset: ['USDC', 'WETH', 'rsETH'][i], withdrawable_ratio_bps: b }))
    render(<MemoryRouter><OverviewView s={s} /></MemoryRouter>)
    const bars = screen.getAllByTestId('position-row').map((r) => within(r).getByRole('progressbar'))
    expect(bars.map((b) => b.getAttribute('data-tone'))).toEqual(['ok', 'warn', 'bad'])
    expect(bars.map((b) => b.getAttribute('aria-valuenow'))).toEqual(['100', '70', '40'])
  })
})

describe('Alerts (T6-10)', () => {
  it('approve posts the exact body', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    localStorage.setItem('sh.operator', 'jury-demo')
    const d = { id: 'DEC-fuji-45201812-1', created_at: '2026-10-11T08:00:26Z', network: 'fuji', block_number: 45201812, alert_ids: [], severity: 'critical',
      exposure_usd: 1, withdrawable_usd: 1, exit_cost_bps: 0, matrix_cell: 'x', rationale: 'r', inputs_hash: '0x', rules_version: 's', playbook_version: 'p',
      record_hash: null, anchor_tx: null, anchor_block: null,
      actions: [
        { type: 'NOTIFY', mode: 'auto', status: 'executed', params: {}, tx_hash: null, amount: null, executed_at: null, note: null },
        { type: 'PAUSE_DEPOSITS', mode: 'auto', status: 'executed', params: {}, tx_hash: null, amount: null, executed_at: null, note: null },
        { type: 'UNPAUSE_DEPOSITS', mode: 'human', status: 'pending_approval', params: {}, tx_hash: null, amount: null, executed_at: null, note: null },
      ] }
    const f = vi.fn((u: string, _i?: RequestInit) => u.includes('/api/decisions') && !u.includes('approve') ? json([d]) : u.includes('/api/alerts') ? json([]) : u.includes('approve') ? json(d) : json(stateFixture))
    vi.stubGlobal('fetch', f)
    renderAt('/alerts')
    await userEvent.click(await screen.findByTestId('approve-DEC-fuji-45201812-1-2'))
    await waitFor(() => expect(f.mock.calls.some((c) => c[0].includes('/approve'))).toBe(true))
    const call = f.mock.calls.find((c) => c[0].includes('/approve'))!
    expect(call[0]).toBe('http://localhost:8000/api/decisions/DEC-fuji-45201812-1/approve')
    expect(call[1]?.method).toBe('POST')
    expect(call[1]?.body).toBe('{"action_index":2,"approver":"jury-demo","approve":true}')
  })
})

describe('Evidence (T6-11)', () => {
  it('verify shows MATCH from fixture', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true')
    renderAt('/evidence')
    const btns = await screen.findAllByRole('button', { name: 'Verify' })
    await userEvent.click(btns[0])
    const r = await screen.findByTestId('verify-result')
    expect(r).toHaveAttribute('data-result', 'match')
    expect(r).toHaveTextContent('MATCH')
  })
})

describe('Demo (T6-13)', () => {
  it('random seed is shown and posted', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    vi.spyOn(Math, 'random').mockReturnValue(0.004242)
    const run = { run_id: 'RUN-1-attack-4242', kind: 'attack', variant: 'default', seed: 4242, status: 'running', started_at: '', finished_at: null, params: {}, log: ['hello log'] }
    const f = vi.fn((u: string, _i?: RequestInit) => u.includes('/api/demo/attack') || u.includes('/api/demo/runs') ? json(run) : u.includes('state') ? json(stateFixture) : json([]))
    vi.stubGlobal('fetch', f)
    renderAt('/demo')
    await userEvent.click(await screen.findByTestId('launch-attack'))
    expect(await screen.findByText('Seed 4242')).toBeInTheDocument()
    const call = f.mock.calls.find((c) => c[0].includes('/api/demo/attack'))!
    expect(call[1]?.body).toBe('{"seed":4242,"variant":"default"}')
    expect(await screen.findByText(/hello log/)).toBeInTheDocument()
  })
  it('variant and seed zero', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'false')
    const r = { run_id: 'R', kind: 'attack', variant: 'usdc', seed: 0, status: 'running', started_at: '', finished_at: null, params: {}, log: [] }
    const f = vi.fn((u: string, _i?: RequestInit) => u.includes('/api/demo') ? json(r) : u.includes('state') ? json(stateFixture) : json([]))
    vi.stubGlobal('fetch', f)
    renderAt('/demo')
    await userEvent.selectOptions(await screen.findByTestId('variant-select'), 'usdc')
    await userEvent.type(screen.getByLabelText(/Seed/), '0')
    await userEvent.click(screen.getByTestId('launch-attack'))
    await waitFor(() => expect(f.mock.calls.some((c) => c[0].includes('/api/demo/attack'))).toBe(true))
    expect(f.mock.calls.find((c) => c[0].includes('/api/demo/attack'))![1]?.body).toBe('{"seed":0,"variant":"usdc"}')
  })
})

describe('App in fixture mode (T6-14)', () => {
  it('works with no backend on every route', async () => {
    vi.stubEnv('VITE_USE_FIXTURES', 'true')
    const f = vi.fn(() => Promise.reject(new Error('no backend'))); vi.stubGlobal('fetch', f)
    for (const p of ['/', '/charts', '/alerts', '/incident', '/evidence', '/dependencies', '/metrics', '/demo']) {
      const { unmount } = renderAt(p)
      expect(await screen.findByTestId('fixture-banner')).toHaveTextContent('FIXTURE MODE')
      unmount()
    }
    expect(f).not.toHaveBeenCalled()
  })
})
