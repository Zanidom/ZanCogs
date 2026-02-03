import asyncio
import datetime as dt
from dataclasses import dataclass
from typing import Optional, AsyncIterator, Union

import discord
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import humanize_number

MessageSource = Union[discord.TextChannel, discord.Thread]

@dataclass
class PurgePlan:
    user: discord.User
    days: int
    per_channel_limit: int
    include_archived_threads: bool = True


class ConfirmPurgeView(discord.ui.View):
    def __init__(self, author_id: int, plan: PurgePlan, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.plan = plan
        self.result: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm purge", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.result = False
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class Purge(commands.Cog):
    """Moderation: purge messages by a user across the guild, with confirmation + audit log + threads."""

    def __init__(self, bot):
        self.bot = bot
        self.conf = Config.get_conf(self, identifier=0x5356661955453, force_registration=True)
        self.conf.register_guild(auditlog_channel_id=None)

    @commands.hybrid_group(name="purgeconfig")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def purgeconfig(self, ctx: commands.Context):
        """Configure purge settings."""
        pass

    @purgeconfig.command(name="auditlog")
    async def purge_auditlog(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Set (or clear) the Audit log channel."""
        if channel is None:
            await self.conf.guild(ctx.guild).auditlog_channel_id.set(None)
            await ctx.send("Audit log channel cleared.")
            return

        await self.conf.guild(ctx.guild).auditlog_channel_id.set(channel.id)
        await ctx.send(f"Audit log channel set to {channel.mention}.")

    async def _get_auditlog_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        cid = await self.conf.guild(guild).auditlog_channel_id()
        if not cid:
            return None
 
        ch = guild.get_channel(cid)
        if isinstance(ch, discord.TextChannel):
            return ch

        #Fallback: fetch from API if not cached for reasons?!
        try:
            fetched = await guild.fetch_channel(cid)
            return fetched if isinstance(fetched, discord.TextChannel) else None
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None


    @commands.hybrid_command(name="purgeuser")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_messages=True)
    @commands.bot_has_guild_permissions(manage_messages=True, read_message_history=True)
    async def purge_user(self, ctx: commands.Context, user: discord.User, days: Optional[int] = 7, per_channel_limit: Optional[int] = 2000):
        """
        Delete messages from a user across all text channels + threads (with confirmation).

        user: The user to purge (should work even if they've left, might need to use userid).
        days: Only scan messages newer than this many days (default 7). Set to 0 to scan all time (slow).
        per_channel_limit: Max messages to scan per channel/thread (default 2000).
        """
        if days is None:
            days = 7
        if per_channel_limit is None:
            per_channel_limit = 2000

        days = max(days, 0)
        per_channel_limit = max(100, min(per_channel_limit, 20000))

        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True, thinking=True)

        plan = PurgePlan(user=user, days=days, per_channel_limit=per_channel_limit, include_archived_threads=True)

        #Confirmation UI
        window_txt = "ALL TIME" if days == 0 else f"last {days} day(s)"
        desc = "\n".join(
            [
                f"User: **{user}** (`{user.id}`)",
                f"Scan window: **{window_txt}**",
                f"Max scan cap: **{humanize_number(per_channel_limit)}** messages per channel/thread",
                "",
                "**Includes:** accessible text channels, active threads, and archived threads.",
                "Bulk delete only works for messages newer than 14 days; older ones are deleted one-by-one (slower).",
            ]
        )
        embed = discord.Embed(title="Confirm purge user", description=desc, color=discord.Color.orange())
        embed.set_footer(text="Confirm within 60 seconds.")

        view = ConfirmPurgeView(author_id=ctx.author.id, plan=plan, timeout=60.0)

        if ctx.interaction:
            msg = await ctx.interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            msg = await ctx.send(embed=embed, view=view)

        await view.wait()

        if view.result is not True:
            txt = "Purge cancelled." if view.result is False else "⌛ Purge timed out."
            if ctx.interaction:
                await ctx.interaction.followup.send(txt, ephemeral=True)
            else:
                await ctx.send(txt)
            return

        result = await self._execute_purge(ctx, plan)

        done_text = (
            f"Purge complete for **{user}**.\n"
            f"- Found: **{humanize_number(result['found'])}**\n"
            f"- Deleted: **{humanize_number(result['deleted'])}**\n"
            f"- Sources scanned (channels+threads): **{humanize_number(result['scanned'])}**\n"
            f"- Sources skipped (no access/errors): **{humanize_number(result['skipped'])}**"
        )

        if ctx.interaction:
            await ctx.interaction.followup.send(done_text, ephemeral=True)
        else:
            await ctx.send(done_text)

        await self._send_auditlog(ctx, plan, result)

        #Disable buttons on the confirm prompt
        try:
            for child in view.children:
                child.disabled = True
            await msg.edit(view=view)
        except discord.HTTPException:
            pass

    async def _execute_purge(self, ctx: commands.Context, plan: PurgePlan) -> dict:
        guild = ctx.guild
        assert guild is not None

        now = dt.datetime.now(dt.timezone.utc)
        after = None if plan.days == 0 else (now - dt.timedelta(days=plan.days))
        bulk_cutoff = now - dt.timedelta(days=14)

        total_deleted = 0
        total_found = 0
        sources_scanned = 0
        sources_skipped = 0

        async for src in self._iter_message_sources(guild, include_archived=plan.include_archived_threads):
            if not self._can_work_source(guild, src):
                sources_skipped += 1
                continue

            sources_scanned += 1
            to_bulk = []
            to_single = []

            #calc when we want messages since, allows us to filter on a thread/channel basis
            now = dt.datetime.now(dt.timezone.utc)
            after = None if plan.days == 0 else (now - dt.timedelta(days=plan.days))
            
            try:
                async for msg in src.history(limit=plan.per_channel_limit, after=after, oldest_first=False, after=after):
                    #If we’ve crossed our time window, stop scanning this source.
                    #should save a lot of time across lesser-used threads and channels
                    if after is not None and msg.created_at < after:
                        break
                    
                    if msg.author.id != plan.user.id:
                        continue
                    total_found += 1
                    if msg.created_at >= bulk_cutoff:
                        to_bulk.append(msg)
                    else:
                        to_single.append(msg)

                #Bulk delete in chunks of 100
                #(only possible for newer-than-14-days)
                for i in range(0, len(to_bulk), 100):
                    chunk = to_bulk[i : i + 100]
                    try:
                        await src.delete_messages(
                            chunk,
                            reason=f"Purge user {plan.user} requested by {ctx.author}",
                        )
                        total_deleted += len(chunk)
                    except (discord.Forbidden, discord.HTTPException):
                        #fall back to single deletes if bulk fails for this chunk for whatever reason
                        for msg in chunk:
                            try:
                                await msg.delete(reason=f"Purge user {plan.user} requested by {ctx.author}")
                                total_deleted += 1
                            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                                pass
                            await asyncio.sleep(0.35)

                    await asyncio.sleep(1.0)


                #Single delete older messages
                for msg in to_single:
                    try:
                        await msg.delete(reason=f"Purge user {plan.user} requested by {ctx.author}")
                        total_deleted += 1
                    except (discord.Forbidden, discord.NotFound):
                        pass
                    await asyncio.sleep(0.35)

            except (discord.Forbidden, discord.HTTPException):
                sources_skipped += 1
                continue

        return {
            "found": total_found,
            "deleted": total_deleted,
            "scanned": sources_scanned,
            "skipped": sources_skipped,
            "days": plan.days,
            "per_channel_limit": plan.per_channel_limit,
            "timestamp": now,
            "include_archived_threads": plan.include_archived_threads,
        }

    def _can_work_source(self, guild: discord.Guild, src: MessageSource) -> bool:
        me = guild.me
        if me is None:
            return False

        if isinstance(src, discord.TextChannel):
            perms = src.permissions_for(me)
            return perms.view_channel and perms.read_message_history and perms.manage_messages

        #Thread permissions are inherited; thread has its own permissions_for in d.py
        if isinstance(src, discord.Thread):
            perms = src.permissions_for(me)
            #manage_messages is still needed; read history too
            return perms.view_channel and perms.read_message_history and perms.manage_messages

        return False
    
    def _thread_last_activity(self, th: discord.Thread) -> Optional[dt.datetime]:
        """
        Best-effort last activity time without fetching messages.
        Uses last_message_id snowflake time when possible.
        """
        if th.last_message_id:
            return discord.utils.snowflake_time(th.last_message_id)
        #If there's no last_message_id, fallback to thread creation time.
        return th.created_at

    def _should_scan_thread(self, th: discord.Thread, after: Optional[dt.datetime]) -> bool:
        if after is None:
            return True
        last = self._thread_last_activity(th)
        if last is None:
            #Unknown -> scan (safe default)
            return True
        return last >= after


    async def _iter_message_sources(self, guild: discord.Guild, include_archived: bool, after: Optional[dt.datetime]) -> AsyncIterator[MessageSource]:
        """
        Yield every message source we should scan:
        - each text channel
        - each active thread in that channel
        - (optional) archived threads in that channel (public + private, where accessible)
        """
        for ch in guild.text_channels:
            yield ch

            #Active threads (public/private that are currently active)
            try:
                for th in ch.threads:
                    if self._should_scan_thread(th, after):
                        yield th
            except Exception:
                #Some older d.py versions / edge cases; just skip
                pass

            if not include_archived:
                continue

            #Archived public threads
            try:
                async for th in ch.archived_threads(limit=None):
                    if self._should_scan_thread(th, after):
                        yield th
            except (discord.Forbidden, discord.HTTPException):
                pass

            #Archived private threads (requires Manage Threads)
            try:
                async for th in ch.archived_threads(limit=None, private=True):
                    if self._should_scan_thread(th, after):
                        yield th
            except (discord.Forbidden, discord.HTTPException, TypeError):
                #TypeError if  discord.py version doesn't support private=True for god knows what reason
                pass

    async def _send_auditlog(self, ctx: commands.Context, plan: PurgePlan, result: dict):
        guild = ctx.guild
        if guild is None:
            return

        auditlog = await self._get_auditlog_channel(guild)
        if auditlog is None:
            return

        me = guild.me
        if me and not auditlog.permissions_for(me).send_messages:
            return

        window = "ALL TIME" if plan.days == 0 else f"last {plan.days} day(s)"
        embed = discord.Embed(title="User purge executed", color=discord.Color.red(), timestamp=result["timestamp"])
        embed.add_field(name="Target", value=f"{plan.user} (`{plan.user.id}`)", inline=False)
        embed.add_field(name="Moderator", value=f"{ctx.author} (`{ctx.author.id}`)", inline=False)
        embed.add_field(name="Window", value=window, inline=True)
        embed.add_field(name="Scan cap", value=humanize_number(plan.per_channel_limit), inline=True)
        embed.add_field(name="Includes archived threads", value=str(bool(result["include_archived_threads"])), inline=True)
        embed.add_field(name="Found", value=humanize_number(result["found"]), inline=True)
        embed.add_field(name="Deleted", value=humanize_number(result["deleted"]), inline=True)
        embed.add_field(name="Sources scanned", value=humanize_number(result["scanned"]), inline=True)
        embed.add_field(name="Sources skipped", value=humanize_number(result["skipped"]), inline=True)

        await auditlog.send(embed=embed)
