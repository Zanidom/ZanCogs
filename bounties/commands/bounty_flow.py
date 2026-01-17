from __future__ import annotations

import discord
from redbot.core import app_commands


def register(bounty_group: app_commands.Group, cog):
    
    @bounty_group.command(name="apply", description="Apply to a bounty by id or exact title.")
    @app_commands.guild_only()
    async def apply(interaction: discord.Interaction, key: str):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if bounty.get("open_fulfil"):
            await interaction.response.send_message("This bounty is in open-fulfil mode; use /bounty fulfil.", ephemeral=True)
            return

        if interaction.user.id in bounty.get("blacklist", []):
            await interaction.response.send_message("You are blacklisted from this bounty.", ephemeral=True)
            return

        if str(interaction.user.id) in (bounty.get("accepted") or {}):
            await interaction.response.send_message("You are already accepted for this bounty.", ephemeral=True)
            return

        applicants = bounty.get("applicants", [])
        if interaction.user.id in applicants:
            await interaction.response.send_message("You already applied.", ephemeral=True)
            return

        applicants.append(interaction.user.id)
        bounty["applicants"] = applicants

        await cog._commit(interaction.guild, bounty, audit_text=f"<@{interaction.user.id}> applied to bounty #{bounty['id']}")
        
        owner = interaction.guild.get_member(bounty["owner_id"])
        if owner:
            await cog._try_dm(
                user=owner,
                content=f"{interaction.user.mention} applied for your bounty #{bounty['id']} - {bounty['title']}."
            )

        await interaction.response.send_message("Applied.", ephemeral=True)

    @bounty_group.command(name="accept", description="Accept an applicant (escrows the reward now).")
    @app_commands.guild_only()
    async def accept(interaction: discord.Interaction, key: str, user: discord.Member):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if bounty.get("open_fulfil"):
            await interaction.response.send_message("This bounty is open-fulfil; no accepting needed.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        if user.id in bounty.get("blacklist", []):
            await interaction.response.send_message("That user is blacklisted from this bounty.", ephemeral=True)
            return

        applicants = bounty.get("applicants", [])
        if user.id not in applicants:
            await interaction.response.send_message("That user hasn't applied for this bounty.", ephemeral=True)
            return

        accepted = bounty.get("accepted") or {}
        if str(user.id) in accepted:
            await interaction.response.send_message("That user is already accepted.", ephemeral=True)
            return

        owner = interaction.guild.get_member(bounty["owner_id"])
        if owner is None:
            await interaction.response.send_message("Bounty owner is no longer in this server.", ephemeral=True)
            return

        reward = int(bounty.get("reward", 0))
        if reward <= 0:
            await interaction.response.send_message("This bounty has an invalid reward amount.", ephemeral=True)
            return

        if not await cog.econ.can_spend(owner, reward):
            await interaction.response.send_message(
                "You cannot accept people for this bounty - it's currently too expensive for you.",
                ephemeral=True,
            )
            return

        await cog.econ.withdraw(owner, reward)

        bounty["applicants"] = [uid for uid in applicants if uid != user.id]
        accepted[str(user.id)] = {"escrowed": reward, "submitted": False}
        bounty["accepted"] = accepted

        await cog._try_dm(
            user=user,
            content=f"You were accepted for bounty #{bounty['id']} - {bounty['title']}. Use /bounty fulfil {bounty['id']} when done."
        )

        await cog._commit(interaction.guild, bounty, audit_text=f"<@{interaction.user.id}> accepted <@{user.id}> for bounty #{bounty['id']} (escrowed)")
        await interaction.response.send_message(f"Accepted {user.mention}. Reward escrowed.")


    @bounty_group.command(name="decline", description="Decline an applicant; optionally blacklist them for this bounty.")
    @app_commands.guild_only()
    async def decline(interaction: discord.Interaction, key: str, user: discord.Member, blacklist: bool = False):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        if bounty.get("open_fulfil"):
            await interaction.response.send_message("This bounty is set to open fulfil mode; there are no applicants to decline.", ephemeral=True)
            return

        bounty["applicants"] = [uid for uid in bounty.get("applicants", []) if uid != user.id]
        if blacklist and user.id not in bounty.get("blacklist", []):
            bounty.setdefault("blacklist", []).append(user.id)

        await cog._try_dm(
            user=user,
            content=f"You were declined for bounty #{bounty['id']} - {bounty['title']}."
        )

        await cog._commit(interaction.guild, bounty, audit_text=f"<@{interaction.user.id}> declined <@{user.id}> for bounty #{bounty['id']}")
        await interaction.response.send_message("Done.", ephemeral=True)

    @bounty_group.command(name="unaccept", description="Remove an accepted user; optionally blacklist; refunds escrow.")
    @app_commands.guild_only()
    async def unaccept(interaction: discord.Interaction, key: str, user: discord.Member, blacklist: bool = False):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if bounty.get("open_fulfil"):
            await interaction.response.send_message("Open-fulfil bounties do not have accepted users.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        accepted = bounty.get("accepted") or {}
        st = accepted.pop(str(user.id), None)
        if not st:
            await interaction.response.send_message("That user is not accepted for this bounty.", ephemeral=True)
            return

        owner = interaction.guild.get_member(bounty["owner_id"])
        if owner:
            await cog.econ.deposit(owner, int(st.get("escrowed", 0)))

        if blacklist and user.id not in bounty.get("blacklist", []):
            bounty.setdefault("blacklist", []).append(user.id)

        bounty["accepted"] = accepted

        
        await cog._try_dm(
            user=user,
            content=f"You were unaccepted for bounty #{bounty['id']} - {bounty['title']}."
        )

        await cog._commit(interaction.guild, bounty, audit_text=f"↩️ <@{interaction.user.id}> unaccepted <@{user.id}> for bounty #{bounty['id']} (refund)")
        await interaction.response.send_message("Removed and refunded escrow.", ephemeral=True)

    @bounty_group.command(name="fulfil", description="Mark a bounty as completed (request payout).")
    @app_commands.guild_only()
    async def fulfil(interaction: discord.Interaction, key: str):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if bounty.get("open_fulfil"):
            subs = bounty.get("submissions") or {}
            subs[str(interaction.user.id)] = True
            bounty["submissions"] = subs
            await cog._commit(interaction.guild, bounty, audit_text=f"<@{interaction.user.id}> submitted fulfilment for open bounty #{bounty['id']}")
            await interaction.response.send_message("Submission recorded. Awaiting payout.", ephemeral=True)
            return

        accepted = bounty.get("accepted") or {}
        st = accepted.get(str(interaction.user.id))
        if not st:
            await interaction.response.send_message("You are not accepted for this bounty.", ephemeral=True)
            return

        st["submitted"] = True
        accepted[str(interaction.user.id)] = st
        bounty["accepted"] = accepted

        owner = interaction.guild.get_member(bounty["owner_id"])
        if owner:
            await cog._try_dm(
                user=owner,
                content=f"{interaction.user.mention} marked fulfilment for bounty #{bounty['id']} - {bounty['title']}."
            )

        await cog._commit(interaction.guild, bounty, audit_text=f"<@{interaction.user.id}> marked fulfilment for bounty #{bounty['id']}")
        await interaction.response.send_message("Marked as fulfilled. Awaiting payout.", ephemeral=True)

    @bounty_group.command(name="payout", description="Approve completion and pay out (owner/admin).")
    @app_commands.guild_only()
    async def payout(interaction: discord.Interaction, key: str, user: discord.Member):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        if int(bounty.get("max_payouts", 0)) <= 0:
            await interaction.response.send_message("This bounty has no remaining payouts.", ephemeral=True)
            return

        reward = int(bounty.get("reward", 0))

        if bounty.get("open_fulfil"):
            owner = interaction.guild.get_member(bounty["owner_id"])
            if owner is None:
                await cog.board.delete(interaction.guild, bounty)
                await cog.store.delete(interaction.guild, bounty["id"])
                await cog.audit.log(interaction.guild, f"Removed orphaned bounty #{bounty['id']} (owner missing)")
                await interaction.response.send_message("Owner missing; bounty removed.", ephemeral=True)
                return

            if not await cog.econ.can_spend(owner, reward):
                await cog.board.delete(interaction.guild, bounty)
                await cog.store.delete(interaction.guild, bounty["id"])
                await cog.audit.log(interaction.guild, f"Removed open bounty #{bounty['id']} (owner couldn't afford payout)")
                await interaction.response.send_message("Owner can't afford payout; bounty removed.", ephemeral=True)
                return

            await cog.econ.withdraw(owner, reward)
            await cog.econ.deposit(user, reward)

            bounty["max_payouts"] = int(bounty["max_payouts"]) - 1
            if bounty["max_payouts"] <= 0:
                await cog.board.delete(interaction.guild, bounty)
                await cog.store.delete(interaction.guild, bounty["id"])
                await cog.audit.log(interaction.guild, f"Open bounty #{bounty['id']} completed and removed (paid <@{user.id}>)")
            else:
                await cog._commit(interaction.guild, bounty, audit_text=f"Open bounty #{bounty['id']} paid out to <@{user.id}> by <@{interaction.user.id}>")

            await interaction.response.send_message(f"Paid {user.mention}.")
            return

        accepted = bounty.get("accepted") or {}
        st = accepted.get(str(user.id))
        if not st:
            await interaction.response.send_message("That user isn't accepted for this bounty.", ephemeral=True)
            return
        if not st.get("submitted"):
            await interaction.response.send_message("That user hasn't marked fulfilment yet.", ephemeral=True)
            return

        amount = int(st.get("escrowed", 0))
        await cog.econ.deposit(user, amount)

        accepted.pop(str(user.id), None)
        bounty["accepted"] = accepted
        bounty["max_payouts"] = int(bounty["max_payouts"]) - 1

        if bounty["max_payouts"] <= 0:
            await cog.board.delete(interaction.guild, bounty)
            await cog.store.delete(interaction.guild, bounty["id"])
            await cog.audit.log(interaction.guild, f"Bounty #{bounty['id']} fully completed and removed (paid <@{user.id}>)")
        else:
            await cog._commit(interaction.guild, bounty, audit_text=f"Bounty #{bounty['id']} paid out to <@{user.id}> by <@{interaction.user.id}>")

        await interaction.response.send_message(f"Paid {user.mention}.")

    @bounty_group.command(name="rebuke", description="Reject a fulfilment attempt; optionally revoke and refund escrow.")
    @app_commands.guild_only()
    async def rebuke(interaction: discord.Interaction, key: str, user: discord.Member, revoke: bool = False):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        if bounty.get("open_fulfil"):
            subs = bounty.get("submissions") or {}
            if str(user.id) not in subs:
                await interaction.response.send_message("That user has not submitted fulfilment.", ephemeral=True)
                return
            subs.pop(str(user.id), None)
            bounty["submissions"] = subs
            await cog._commit(interaction.guild, bounty, audit_text=f"Open bounty #{bounty['id']} rebuked submission from <@{user.id}> by <@{interaction.user.id}>")
            await interaction.response.send_message("Rebuked (submission removed).", ephemeral=True)
            return

        accepted = bounty.get("accepted") or {}
        st = accepted.get(str(user.id))
        if not st:
            await interaction.response.send_message("That user isn't accepted for this bounty.", ephemeral=True)
            return

        if revoke:
            accepted.pop(str(user.id), None)
            owner = interaction.guild.get_member(bounty["owner_id"])
            if owner:
                await cog.econ.deposit(owner, int(st.get("escrowed", 0)))
        else:
            st["submitted"] = False
            accepted[str(user.id)] = st

        bounty["accepted"] = accepted
        await cog._commit(interaction.guild, bounty, audit_text=f"Bounty #{bounty['id']} rebuked <@{user.id}> by <@{interaction.user.id}>")
        await interaction.response.send_message("Rebuked.", ephemeral=True)

    @bounty_group.command(name="remove", description="Remove a bounty by id or exact title (owner/admin).")
    @app_commands.guild_only()
    async def remove(interaction: discord.Interaction, key: str):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await cog._blocked(interaction):
            return

        bounty = await cog.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if not await cog._require_owner_or_admin(interaction, bounty):
            return

        if not bounty.get("open_fulfil"):
            accepted = bounty.get("accepted") or {}
            if accepted:
                owner = interaction.guild.get_member(bounty["owner_id"])
                if owner:
                    refund = sum(int(v.get("escrowed", 0)) for v in accepted.values())
                    if refund:
                        await cog.econ.deposit(owner, refund)

        await cog.board.delete(interaction.guild, bounty)
        await cog.store.delete(interaction.guild, bounty["id"])
        await cog.audit.log(interaction.guild, f"Bounty #{bounty['id']} removed by <@{interaction.user.id}>")
        await interaction.response.send_message("Bounty removed.", ephemeral=True)
