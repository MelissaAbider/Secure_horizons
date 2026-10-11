import { siDiscord, siSlack, siTelegram } from 'simple-icons'

export type Channel = 'discord' | 'telegram' | 'slack' | 'email'

const BRANDS = { discord: siDiscord, telegram: siTelegram, slack: siSlack } as const
export const CHANNEL_NAMES: Record<Channel, string> = { discord: 'Discord', telegram: 'Telegram', slack: 'Slack', email: 'Email' }

/** Brand logo of an alert channel (Simple Icons, CC0); a plain envelope for email. */
export function ChannelLogo({ channel, className = 'h-5 w-5' }: { channel: Channel; className?: string }) {
  if (channel === 'email') {
    return (
      <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none" stroke="#5F6B7A" strokeWidth="1.8" strokeLinejoin="round">
        <rect x="3" y="5" width="18" height="14" rx="2.5" /><path d="m4 7 8 6 8-6" />
      </svg>
    )
  }
  const icon = BRANDS[channel]
  return <svg viewBox="0 0 24 24" className={className} aria-hidden fill={`#${icon.hex}`}><path d={icon.path} /></svg>
}
