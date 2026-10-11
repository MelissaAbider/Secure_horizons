import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ruleHints, isAddress, stepsDone, defaultSetup } from '../lib/setup'
import type { SafeStatus } from '../lib/safeApi'
import { Setup } from './Setup'

const OWNER = '0x' + 'a1'.repeat(20)
const SAFE = '0x' + 'b2'.repeat(20)
const INTEGRATIONS = [
  { id: 'lend-eth:WETH', protocol: 'lend-eth', asset: 'WETH', label: 'Lending protocol, Ethereum deployment · WETH' },
  { id: 'lend-avax:USDC', protocol: 'lend-avax', asset: 'USDC', label: 'Lending protocol, Avalanche deployment · USDC' },
]
const base: SafeStatus = { network: 'fuji', chain_id: 43113, explorer_url: 'https://testnet.snowtrace.io', integrations_available: INTEGRATIONS, connected: false }
let current: SafeStatus = base
const signed: string[] = []

vi.mock('../lib/safeApi', () => ({
  safeApi: {
    status: vi.fn(async () => current),
    connect: vi.fn(async () => { current = { ...base, connected: true, owner: OWNER, safe: SAFE, module_enabled: false, seal_status: 'none' }; return current }),
    prepare: vi.fn(async (action: string) => ({ safe_tx_hash: `0x${action}`, typed_data: { action }, summary: action, action })),
    submit: vi.fn(async (hash: string) => {
      current = hash === '0xseal'
        ? { ...current, seal_status: 'sealed', sealed_integrations: ['lend-eth:WETH', 'lend-avax:USDC'] }
        : { ...current, module_enabled: true }
      return { tx_hash: '0x1', status: current }
    }),
  },
}))
vi.mock('../lib/wallet', () => ({
  hasWallet: () => true,
  connectWallet: vi.fn(async () => OWNER),
  signTypedData: vi.fn(async (_owner: string, typed: { action: string }) => { signed.push(typed.action); return '0xsig' }),
  walletError: (e: unknown) => String(e),
}))
// the live panels poll the backend: covered by their own checks, stubbed here
vi.mock('../components/LiveDemo', () => ({ LiveDemo: () => <div data-testid="live-demo" /> }))
vi.mock('../components/SafePanel', () => ({ SafePanel: () => <div data-testid="safe-panel" /> }))

describe('Setup page', () => {
  it('connects the wallet, signs the module and the seal, then goes live', async () => {
    render(<MemoryRouter><Setup /></MemoryRouter>)
    expect(screen.getByTestId('setup-count')).toHaveTextContent('0 of 4 steps done')
    await userEvent.click(screen.getByTestId('connect-safe'))
    await waitFor(() => expect(screen.getByTestId('setup-count')).toHaveTextContent('1 of 4 steps done'))
    expect(signed).toEqual(['enable_module'])
    await userEvent.click(await screen.findByTestId('seal'))
    await waitFor(() => expect(screen.getByTestId('setup-count')).toHaveTextContent('2 of 4 steps done'))
    expect(signed).toEqual(['enable_module', 'seal'])
    expect(await screen.findByTestId('rule-hint')).toHaveTextContent('Never more than 30% on Aave')
    await userEvent.click(screen.getByTestId('save-agent'))
    expect(screen.queryByTestId('live-demo')).toBeNull()
    await userEvent.click(screen.getByTestId('go-live'))
    expect(screen.getByTestId('setup-count')).toHaveTextContent('4 of 4 steps done')
    expect(screen.getByTestId('guard-status')).toHaveTextContent('Watching Avalanche Fuji')
    expect(screen.getByTestId('live-demo')).toBeInTheDocument()
    expect(screen.getByTestId('safe-panel')).toBeInTheDocument()
  })
  it('helpers', () => {
    expect(isAddress(OWNER)).toBe(true)
    expect(isAddress('0xabc')).toBe(false)
    expect(ruleHints('Jamais plus de 25 % sur Benqi', ['benqi-usdc'])).toEqual([{ line: 'Jamais plus de 25 % sur Benqi', protocolId: 'benqi-usdc', pct: 25 }])
    expect(stepsDone(defaultSetup())).toEqual([false, false, false, false])
  })
})
