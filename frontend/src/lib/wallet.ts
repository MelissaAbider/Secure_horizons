// Browser wallet (Rabby, or any EIP-1193 wallet): connect on the backend's chain and sign the Safe transactions.
// The wallet only signs typed data: the platform relays and pays the gas, and never sees the key.

interface Eip1193 { request(args: { method: string; params?: unknown[] }): Promise<unknown> }
declare global { interface Window { ethereum?: Eip1193 } }

const CHAINS: Record<number, { chainName: string; rpcUrls: string[]; blockExplorerUrls: string[] }> = {
  43113: { chainName: 'Avalanche Fuji C-Chain', rpcUrls: ['https://api.avax-test.network/ext/bc/C/rpc'], blockExplorerUrls: ['https://testnet.snowtrace.io'] },
  31337: { chainName: 'Anvil (local)', rpcUrls: ['http://127.0.0.1:8545'], blockExplorerUrls: [] },
}

// EIP-6963: each installed wallet announces itself (name, icon, rdns), so Rabby is used even next to MetaMask
interface Announced { info: { uuid: string; name: string; icon: string; rdns: string }; provider: Eip1193 }
const announced: Announced[] = []
if (typeof window !== 'undefined') {
  window.addEventListener('eip6963:announceProvider', (e) => {
    const d = (e as CustomEvent<Announced>).detail
    if (d && !announced.some((x) => x.info.uuid === d.info.uuid)) announced.push(d)
  })
  window.dispatchEvent(new Event('eip6963:requestProvider'))
}

export function hasWallet(): boolean { return typeof window !== 'undefined' && (announced.length > 0 || !!window.ethereum) }

function wallet(): Eip1193 {
  const rabby = announced.find((d) => d.info.rdns === 'io.rabby')?.provider
  const any = rabby ?? window.ethereum ?? announced[0]?.provider
  if (!any) throw new Error('No browser wallet found: install Rabby and turn on testnets.')
  return any
}

/** Asks for the account, then switches the wallet to the backend's chain (adding it when unknown). */
export async function connectWallet(chainId: number): Promise<string> {
  const accounts = await wallet().request({ method: 'eth_requestAccounts' }) as string[]
  if (!accounts?.length) throw new Error('The wallet returned no account.')
  const hex = '0x' + chainId.toString(16)
  try {
    await wallet().request({ method: 'wallet_switchEthereumChain', params: [{ chainId: hex }] })
  } catch (e) {
    const code = (e as { code?: number }).code
    const known = CHAINS[chainId]
    if (code !== 4902 || !known) throw e
    await wallet().request({
      method: 'wallet_addEthereumChain',
      params: [{ chainId: hex, nativeCurrency: { name: 'AVAX', symbol: 'AVAX', decimals: 18 }, ...known }],
    })
  }
  return accounts[0]
}

/** Drops this site's access in the wallet (EIP-2255) so the next connect asks again; ignored where unsupported. */
export async function disconnectWallet(): Promise<void> {
  try { await wallet().request({ method: 'wallet_revokePermissions', params: [{ eth_accounts: {} }] }) } catch { /* not supported */ }
}

/** EIP-712 signature of a Safe transaction prepared by the backend. */
export async function signTypedData(account: string, typedData: unknown): Promise<string> {
  return await wallet().request({ method: 'eth_signTypedData_v4', params: [account, JSON.stringify(typedData)] }) as string
}

export function walletError(e: unknown): string {
  const code = (e as { code?: number }).code
  if (code === 4001) return 'Request rejected in the wallet.'
  return e instanceof Error ? e.message : String(e)
}
