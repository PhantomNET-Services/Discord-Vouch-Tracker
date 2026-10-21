# Vouch Tracker

A Red-DiscordBot cog with clean, consistent embeds and a paginated vouch leaderboard.

## Features

- Automatic role-based vouches in a configured text channel.
- Modern embeds with guild branding, member avatars and timestamps.
- Medal rankings for the top three members, with ten members per page.
- Previous/Next buttons (only the command invoker can switch pages).
- Vouch leaderboard cooldown of 30 seconds for non-admins.
- Admin commands for manually adding/removing counts and configuring roles/channel.
- Positive-amount validation, safe nonnegative totals and duplicate-mention handling.
- Original storage identifiers and settings preserved for existing deployments.

## Installation

Use your configured Red-DiscordBot repository or copy the `vouchtracker` folder
into a repo that Red can install from. Then load the cog:

```text
[p]cog install <repository-name> vouchtracker
[p]load vouchtracker
```

Both text commands and hybrid slash commands are provided:

| Command | Purpose |
| --- | --- |
| `vouches <member>` | Show a member's vouch total |
| `vouchleaderboard` | Open the paginated leaderboard |
| `addvouch <member> <amount>` | Admin: add vouches |
| `removevouch <member> <amount>` | Admin: remove vouches |
| `setvouchchannel <channel>` | Admin: set the tracked channel |
| `setvouchroles <role1> [role2] ... [role5]` | Admin: set eligible roles |

## Notes

The cog requires the Discord member intent to read member lists for the
leaderboard. It also needs message-content access for prefix commands and
message-based vouch tracking, plus permission to embed links and send messages.

Counts are stored with the original Config identifier (`1234567890`).
The leaderboard includes members currently in the guild member cache.
