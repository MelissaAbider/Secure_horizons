# Withdraw from the Discord alert

When the fraud is detected, the Discord summary carries one button per sealed integration in the alert scope
("Withdraw WETH from lend-eth") and "Withdraw all to the Safe". A click withdraws the whole position through the
teller-window module, inside the sealed list, back to the Safe: the same path as the dashboard's allocate. The
click and its outcome (transactions with explorer links) appear on the dashboard, Live monitoring, Discord card.

Code: `backend/discord_actions.py`, routes in `backend/api/response.py`, tests `backend/tests/test_t4_discord_actions.py`.

## Guards

- Discord's Ed25519 signature is checked on every request (`DISCORD_PUBLIC_KEY`); a bad signature gets 401.
- Only Discord users listed in `DISCORD_ALLOWED_USER_IDS` can act; an empty list refuses every click.
- Only our fixed button ids are accepted (`sh:withdraw:<protocol>:<asset>`, `sh:withdraw:all`); text never maps to an action.
- Funds only go back to the Safe; the sealed list still applies on-chain. No new key: the operator key already used by the dashboard.
- `DRY_RUN_ACTIONS=true` (default): the click is recorded as `simulated` and nothing is sent. Set `false` on Fuji for real withdrawals.

## Setup (once)

1. https://discord.com/developers/applications → New Application. Copy the **Public Key** → `DISCORD_PUBLIC_KEY`.
2. Bot tab → Reset Token → `DISCORD_BOT_TOKEN` (secret, `.env` only). Invite the bot to the server
   (OAuth2 → URL Generator, scope `bot`, permissions *Send Messages*, *Embed Links*, *Attach Files*).
3. Discord settings → Advanced → Developer Mode. Right-click the alert channel → Copy Channel ID → `DISCORD_CHANNEL_ID`.
   Right-click each allowed member → Copy User ID → `DISCORD_ALLOWED_USER_IDS` (comma-separated).
4. The backend must be reachable over HTTPS. On the VM or a laptop: `cloudflared tunnel --url http://localhost:8000`.
5. General Information → **Interactions Endpoint URL** = `https://<tunnel>/api/discord/interactions` → Save
   (Discord sends a signed PING; the backend must be running with `DISCORD_PUBLIC_KEY` set).
6. Restart the backend. `GET /api/discord/config` should return `{"buttons": true, "interactions": true, "allowed_users": N}`.

Without the bot settings the alert still goes out through `ALERT_WEBHOOK_URL`, without buttons.
