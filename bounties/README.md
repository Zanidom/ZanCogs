# Bounties (Red-DiscordBot Cog)

A slash-command cog that lets users post bounties, apply/accept with escrow, and pay out via the Bank.

## Commands
- `/bounty add` (modal)
- `/bounty list`
- `/bounty view <id|title>`
- `/bounty board`
- `/bounty mine`
- `/bounty apply <id|title>`
- `/bounty accept <id|title> <user>`
- `/bounty decline <id|title> <user> [blacklist]`
- `/bounty unaccept <id|title> <user> [blacklist]`
- `/bounty fulfil <id|title>`
- `/bounty payout <id|title> <user>`
- `/bounty rebuke <id|title> <user> [revoke]`
- `/bounty edit <id|title>` (modal)
- `/bounty remove <id|title>`

Config (admins):
- `/bountyconfig audit_channel <channel-or-thread>`
- `/bountyconfig board_channel <channel-or-thread>`
- `/bountyconfig add_cost <amount>`
- `/bountyconfig block <user>`
- `/bountyconfig unblock <user>`

## Setup
1. Load the cog.
2. Set audit/board channels:
   - `/bountyconfig audit_channel #your-channel`
   - `/bountyconfig board_channel #your-channel`
3. Sync slash commands using your usual Red slash sync process (e.g. `[p]slash sync` / `[p]slash enable` depending on your Red version & setup).

## Notes
- The board keeps **one message per bounty** and edits embeds in-place when bounties change.
- Views (buttons) are not persistent across bot restarts in this v1; commands still work.
