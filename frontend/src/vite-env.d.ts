/// <reference types="vite/client" />
declare const __EXPLORER_URL__: string

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_USE_FIXTURES?: string
  readonly VITE_HASH_ROUTER?: string
}
