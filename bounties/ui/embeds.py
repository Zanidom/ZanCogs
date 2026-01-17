from __future__ import annotations
from typing import Any
import discord


def build_bounty_embed(guild: discord.Guild, bounty: dict[str, Any]) -> discord.Embed:
    owner = guild.get_member(bounty["owner_id"])
    owner_name = owner.display_name if owner else f"<@{bounty['owner_id']}>"

    e = discord.Embed(
        title=f"#{bounty['id']} - {bounty['title']}",
        description=(bounty.get("desc") or "")[:4000],
    )
    e.add_field(name="Reward", value=str(bounty["reward"]), inline=True)
    e.add_field(name="Remaining payouts", value=str(bounty["max_payouts"]), inline=True)
    e.add_field(name="Open fulfil", value="Yes" if bounty.get("open_fulfil") else "No", inline=True)
    e.add_field(name="Posted by", value=owner_name, inline=False)

    if bounty.get("created_at"):
        e.add_field(name="Created", value=bounty["created_at"], inline=True)
    if bounty.get("updated_at"):
        e.add_field(name="Updated", value=bounty["updated_at"], inline=True)

    if bounty.get("open_fulfil"):
        subs = bounty.get("submissions", {}) or {}
        if subs:
            e.add_field(name="Submissions", value="\n".join(f"<@{uid}>" for uid in subs.keys())[:1024], inline=False)
    else:
        applicants = bounty.get("applicants", []) or []
        accepted = bounty.get("accepted", {}) or {}
        if applicants:
            e.add_field(name="Applicants", value="\n".join(f"<@{uid}>" for uid in applicants)[:1024], inline=False)
        if accepted:
            lines = []
            for uid, st in accepted.items():
                lines.append(f"<@{uid}>")
            e.add_field(name="Accepted", value="\n".join(lines)[:1024], inline=False)

    e.set_footer(text="Use /bounty view to show one bounty, or /bounty board to browse.")
    return e
