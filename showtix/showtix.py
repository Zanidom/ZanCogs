import contextlib
import datetime
import logging
import time
from typing import Optional

import discord
from redbot.core import bank, checks, commands, Config

log = logging.getLogger("red.zancogs.showtix")

LIST_HEADER = "🎟️ **Guest list:**"


class ShowTix(commands.Cog):
    """Self-service shows (temporary voice channels) and guest-list threads.

    Based on ShowTix by MomoandGemini (https://github.com/MomotheWingedLemur/Red-Cogs),
    reworked for multiple concurrent sellers, deposits, and auto-closing shows.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8273645192, force_registration=True)
        self.config.register_guild(
            category_id=None,       # category that show voice channels are created under
            thread_home_id=None,    # text channel that guest-list threads are created in
            fee=100,                # deposit charged on open, refunded on complete
            duration_hours=24,      # shows auto-close (deposit forfeited) after this long
            max_shows=5,            # open shows per guild
            shows={},               # str(owner_id) -> {name, channel_id, opened_at, deposit, holders}
            threads={},             # str(thread_id) -> {name, owner, message_id, members}
        )
        self._autoclose = bot.loop.create_task(self._autoclose_loop())

    def cog_unload(self):
        self._autoclose.cancel()

    # ------------------------------------------------------------- shows

    @commands.guild_only()
    @commands.group(aliases=["st"])
    async def showtix(self, ctx: commands.Context):
        """Open shows, sell tickets, and manage guest-list threads."""
        pass

    @showtix.command(name="open")
    async def show_open(self, ctx: commands.Context, *, name: str):
        """Open a show: pays the deposit and creates your private voice channel.

        Complete it with `[p]showtix complete` to get the deposit back;
        letting it hit the auto-close window forfeits the deposit.
        """
        conf = self.config.guild(ctx.guild)
        category_id = await conf.category_id()
        category = ctx.guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            return await ctx.send("No show category is configured. An admin needs to run "
                f"`{ctx.clean_prefix}showtixset category` first.")

        shows = await conf.shows()
        if str(ctx.author.id) in shows:
            return await ctx.send("You already have a show open. Finish it with "
                f"`{ctx.clean_prefix}showtix complete` before opening another.")
        if len(shows) >= await conf.max_shows():
            return await ctx.send("The venue is full - the maximum number of shows are already running.")

        fee = await conf.fee()
        if fee > 0:
            if not await bank.can_spend(ctx.author, fee):
                currency = await bank.get_currency_name(ctx.guild)
                return await ctx.send(f"The deposit is {fee} {currency} and you can't cover it.")
            await bank.withdraw_credits(ctx.author, fee)

        name = name[:90]
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            ctx.guild.me: discord.PermissionOverwrite(
                view_channel=True, connect=True, manage_channels=True, manage_permissions=True),
            ctx.author: discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, stream=True),
        }
        try:
            channel = await ctx.guild.create_voice_channel(
                f"🎟️ {name}", category=category, overwrites=overwrites,
                reason=f"ShowTix: opened by {ctx.author} ({ctx.author.id})")
        except discord.Forbidden:
            if fee > 0:
                await bank.deposit_credits(ctx.author, fee)
            return await ctx.send("I couldn't create the channel (missing Manage Channels "
                "on that category). Your deposit has been returned.")

        duration = await conf.duration_hours()
        closes_at = int(time.time()) + duration * 3600
        async with conf.shows() as live:
            live[str(ctx.author.id)] = {
                "name": name, "channel_id": channel.id,
                "opened_at": int(time.time()), "deposit": fee, "holders": [],
            }
        deposit_note = ""
        if fee > 0:
            currency = await bank.get_currency_name(ctx.guild)
            deposit_note = (f" Your {fee} {currency} deposit comes back with "
                f"`{ctx.clean_prefix}showtix complete` - if the show auto-closes, it doesn't.")
        await ctx.send(f"🎬 **The show is on!** {channel.mention} is yours until <t:{closes_at}:t> "
            f"(<t:{closes_at}:R>). Sell tickets with `{ctx.clean_prefix}showtix add @user`.{deposit_note}")

    @showtix.command(name="add")
    async def show_add(self, ctx: commands.Context, member: discord.Member):
        """Give someone a ticket to your show."""
        show, channel = await self._own_show(ctx)
        if not show:
            return
        try:
            await channel.set_permissions(member, view_channel=True, connect=True,
                reason=f"ShowTix ticket from {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("I couldn't edit the channel permissions for that user.")
        async with self.config.guild(ctx.guild).shows() as shows:
            holders = shows[str(ctx.author.id)]["holders"]
            if member.id not in holders:
                holders.append(member.id)
        await ctx.send(f"🎟️ **Admit one!** {member.display_name} now has access to {channel.mention}.")

    @showtix.command(name="remove")
    async def show_remove(self, ctx: commands.Context, member: discord.Member):
        """Revoke someone's ticket to your show."""
        show, channel = await self._own_show(ctx)
        if not show:
            return
        async with self.config.guild(ctx.guild).shows() as shows:
            holders = shows[str(ctx.author.id)]["holders"]
            if member.id not in holders:
                return await ctx.send(f"{member.display_name} doesn't hold a ticket to your show.")
            holders.remove(member.id)
        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
            await channel.set_permissions(member, overwrite=None,
                reason=f"ShowTix ticket revoked by {ctx.author}")
        await ctx.send(f"🚫 Ticket revoked - {member.display_name} no longer has access.")

    @showtix.command(name="complete")
    async def show_complete(self, ctx: commands.Context):
        """End your show, tear down its channel, and get your deposit back."""
        show, channel = await self._own_show(ctx)
        if not show:
            return
        await self._close_show(ctx.guild, str(ctx.author.id), show, refund=True)
        note = ""
        if show["deposit"] > 0:
            currency = await bank.get_currency_name(ctx.guild)
            note = f" Your {show['deposit']} {currency} deposit is back in your account."
        await ctx.send(f"👏 **That's a wrap!** The show is over and the channel is gone.{note}")

    @showtix.command(name="list")
    async def show_list(self, ctx: commands.Context):
        """List the shows currently running."""
        shows = await self.config.guild(ctx.guild).shows()
        if not shows:
            return await ctx.send("No shows are running right now.")
        duration = await self.config.guild(ctx.guild).duration_hours()
        lines = []
        for owner_id, show in shows.items():
            closes = show["opened_at"] + duration * 3600
            lines.append(f"**{show['name']}** - <@{owner_id}>, {len(show['holders'])} "
                f"ticket(s), closes <t:{closes}:R>")
        await ctx.send("\n".join(lines)[:2000],
            allowed_mentions=discord.AllowedMentions.none())

    async def _own_show(self, ctx):
        """Fetch the caller's show record and channel, complaining if absent."""
        shows = await self.config.guild(ctx.guild).shows()
        show = shows.get(str(ctx.author.id))
        if not show:
            await ctx.send(f"You don't have a show open. Start one with `{ctx.clean_prefix}showtix open <name>`.")
            return None, None
        channel = ctx.guild.get_channel(show["channel_id"])
        if channel is None:
            # channel was deleted out from under us - clean the record up
            await self._close_show(ctx.guild, str(ctx.author.id), show, refund=True)
            await ctx.send("Your show's channel seems to have been deleted, so I've closed the "
                "show and returned your deposit.")
            return None, None
        return show, channel

    async def _close_show(self, guild: discord.Guild, owner_id: str, show: dict, refund: bool):
        channel = guild.get_channel(show["channel_id"])
        if channel is not None:
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                await channel.delete(reason="ShowTix: show closed")
        if refund and show["deposit"] > 0:
            member = guild.get_member(int(owner_id))
            if member is not None:
                with contextlib.suppress(Exception):
                    await bank.deposit_credits(member, show["deposit"])
        async with self.config.guild(guild).shows() as shows:
            shows.pop(owner_id, None)

    async def _autoclose_loop(self):
        """Close expired shows. Deposits are forfeited on auto-close."""
        await self.bot.wait_until_red_ready()
        while True:
            try:
                for guild_id in await self.config.all_guilds():
                    guild = self.bot.get_guild(guild_id)
                    if guild is None:
                        continue
                    try:
                        conf = self.config.guild(guild)
                        duration = await conf.duration_hours()
                        shows = await conf.shows()
                        now = time.time()
                        for owner_id, show in list(shows.items()):
                            if now - show["opened_at"] >= duration * 3600:
                                await self._close_show(guild, owner_id, show, refund=False)
                                member = guild.get_member(int(owner_id))
                                if member is not None:
                                    with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                                        await member.send(f"⏰ Your show **{show['name']}** hit the "
                                            f"{duration}-hour limit and was closed automatically. "
                                            "The deposit is forfeited - close on time next time!")
                    except Exception:
                        log.exception("Autoclose failed for guild %s", guild_id)
            except Exception:
                log.exception("Autoclose sweep failed")
            await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(minutes=10))

    # ------------------------------------------------------------ threads

    @showtix.group(name="thread")
    async def st_thread(self, ctx: commands.Context):
        """Private guest-list threads - lighter than a show, no expiry."""
        pass

    @st_thread.command(name="create")
    async def thread_create(self, ctx: commands.Context, *, name: str):
        """Create a private thread you control the guest list for."""
        home_id = await self.config.guild(ctx.guild).thread_home_id()
        home = ctx.guild.get_channel(home_id) if home_id else None
        if not isinstance(home, discord.TextChannel):
            return await ctx.send("No thread home channel is configured. An admin needs to run "
                f"`{ctx.clean_prefix}showtixset threadhome` first.")
        try:
            thread = await home.create_thread(name=name[:90],
                type=discord.ChannelType.private_thread, invitable=False,
                reason=f"ShowTix thread by {ctx.author} ({ctx.author.id})")
        except discord.Forbidden:
            return await ctx.send("I can't create private threads in the configured channel.")
        await thread.add_user(ctx.author)
        msg = await thread.send(f"{LIST_HEADER}\n*(empty)*")
        async with self.config.guild(ctx.guild).threads() as threads:
            threads[str(thread.id)] = {"name": name[:90], "owner": ctx.author.id,
                "message_id": msg.id, "members": []}
        await ctx.send(f"🧵 {thread.mention} is yours. Add guests with "
            f"`{ctx.clean_prefix}showtix thread add {thread.id} @user` (or run it inside the thread).")

    @st_thread.command(name="add")
    async def thread_add(self, ctx: commands.Context, member: discord.Member,
                         thread: Optional[discord.Thread] = None):
        """Add someone to your thread's guest list (run inside the thread, or name it)."""
        record, thread = await self._own_thread(ctx, thread)
        if not record:
            return
        await thread.add_user(member)
        async with self.config.guild(ctx.guild).threads() as threads:
            members = threads[str(thread.id)]["members"]
            if member.id not in members:
                members.append(member.id)
        await self._update_guest_list(ctx.guild, thread.id)
        await ctx.send(f"🎟️ {member.display_name} added to {thread.mention}.")

    @st_thread.command(name="remove")
    async def thread_remove(self, ctx: commands.Context, member: discord.Member,
                            thread: Optional[discord.Thread] = None):
        """Remove someone from your thread's guest list."""
        record, thread = await self._own_thread(ctx, thread)
        if not record:
            return
        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
            await thread.remove_user(member)
        async with self.config.guild(ctx.guild).threads() as threads:
            members = threads[str(thread.id)]["members"]
            if member.id in members:
                members.remove(member.id)
        await self._update_guest_list(ctx.guild, thread.id)
        await ctx.send(f"🚫 {member.display_name} removed from {thread.mention}.")

    async def _own_thread(self, ctx, thread: Optional[discord.Thread]):
        """Resolve which thread is being managed and check the caller owns it."""
        if thread is None and isinstance(ctx.channel, discord.Thread):
            thread = ctx.channel
        if thread is None:
            await ctx.send("Run this inside the thread, or pass the thread.")
            return None, None
        threads = await self.config.guild(ctx.guild).threads()
        record = threads.get(str(thread.id))
        if record is None:
            await ctx.send("That thread isn't managed by ShowTix.")
            return None, None
        if record["owner"] != ctx.author.id and not await self.bot.is_admin(ctx.author):
            await ctx.send("Only the thread's owner (or an admin) can manage its guest list.")
            return None, None
        return record, thread

    async def _update_guest_list(self, guild: discord.Guild, thread_id: int):
        """Refresh the cosmetic guest-list message. Access is via add_user, so this
        never pings and its failure never affects who can see the thread."""
        threads = await self.config.guild(guild).threads()
        record = threads.get(str(thread_id))
        if record is None:
            return
        thread = guild.get_thread(thread_id)
        if thread is None:
            # auto-archived threads drop out of get_thread(); fetch and revive
            with contextlib.suppress(discord.NotFound, discord.Forbidden, discord.HTTPException):
                thread = await guild.fetch_channel(thread_id)
        if not isinstance(thread, discord.Thread):
            return
        if thread.archived:
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                await thread.edit(archived=False)
        mentions = [f"<@{uid}>" for uid in record["members"]]
        content = f"{LIST_HEADER}\n" + ("\n".join(mentions) if mentions else "*(empty)*")
        if len(content) > 1990:
            content = f"{LIST_HEADER}\n{len(mentions)} guests (too many to list here)."
        try:
            msg = await thread.fetch_message(record["message_id"])
            await msg.edit(content=content, allowed_mentions=discord.AllowedMentions.none())
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                new_msg = await thread.send(content, allowed_mentions=discord.AllowedMentions.none())
                async with self.config.guild(guild).threads() as live:
                    if str(thread_id) in live:
                        live[str(thread_id)]["message_id"] = new_msg.id

    # ------------------------------------------------------------- admin

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @commands.group()
    async def showtixset(self, ctx: commands.Context):
        """Configure ShowTix for this server."""
        pass

    @showtixset.command(name="category")
    async def set_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        """Set the category show voice channels are created under."""
        await self.config.guild(ctx.guild).category_id.set(category.id)
        await ctx.send(f"🎬 Shows will open under **{category.name}**.")

    @showtixset.command(name="threadhome")
    async def set_threadhome(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the text channel guest-list threads are created in."""
        await self.config.guild(ctx.guild).thread_home_id.set(channel.id)
        await ctx.send(f"🧵 Threads will be created in {channel.mention}.")

    @showtixset.command(name="fee")
    async def set_fee(self, ctx: commands.Context, amount: int):
        """Set the show deposit (0 disables it)."""
        await self.config.guild(ctx.guild).fee.set(max(0, amount))
        await ctx.send(f"💰 Show deposit set to {max(0, amount)}.")

    @showtixset.command(name="duration")
    async def set_duration(self, ctx: commands.Context, hours: int):
        """Set how long a show may run before auto-closing (1-72 hours)."""
        hours = max(1, min(72, hours))
        await self.config.guild(ctx.guild).duration_hours.set(hours)
        await ctx.send(f"⏰ Shows now auto-close after {hours} hour(s).")

    @showtixset.command(name="maxshows")
    async def set_maxshows(self, ctx: commands.Context, count: int):
        """Set the maximum number of concurrently open shows (1-25)."""
        count = max(1, min(25, count))
        await self.config.guild(ctx.guild).max_shows.set(count)
        await ctx.send(f"🎪 Up to {count} show(s) can now run at once.")

    @showtixset.command(name="close")
    async def set_close(self, ctx: commands.Context, owner: discord.Member, refund: bool = True):
        """Force-close a user's show (admin). Refunds the deposit unless told otherwise."""
        shows = await self.config.guild(ctx.guild).shows()
        show = shows.get(str(owner.id))
        if not show:
            return await ctx.send(f"{owner.display_name} has no open show.")
        await self._close_show(ctx.guild, str(owner.id), show, refund=refund)
        await ctx.send(f"🛑 Closed **{show['name']}**{' with' if refund else ' without'} a deposit refund.")
