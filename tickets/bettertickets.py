import asyncio
import datetime
import typing

import discord
from redbot.core import Config, checks, commands, app_commands
from redbot.core.bot import Red
from redbot.core.utils import AsyncIter
import traceback

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class TicketError(Exception):
    pass


class TicketPanelView(discord.ui.View):
    """Persistent view attached to the ticket panel message."""

    def __init__(self, cog: "BetterTickets", guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    async def rebuild(self):
        """Rebuild buttons from config cases."""
        self.clear_items()

        guild = self.cog.bot.get_guild(self.guild_id)
        if not guild:
            return

        cases = await self.cog.config.guild(guild).cases()
        for i, (case_key, data) in enumerate(cases.items()):
            #Max 25 buttons according to the Discord API
            #If anyone wants more than that... well tough I guess :upside_down:
            if i >= 25:
                break
            emoji = data.get("emoji") or None
            title = data.get("title") or case_key
            label = title[:80]

            self.add_item(
                TicketCaseButton(
                    case_key=case_key,
                    label=label,
                    emoji=emoji,
                    custom_id=f"bticket:open:{self.guild_id}:{case_key}",
                )
            )


class TicketCaseButton(discord.ui.Button):
    def __init__(self, case_key: str, label: str, emoji: typing.Optional[str], custom_id: str):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label,
            emoji=emoji,
            custom_id=custom_id,
        )
        self.case_key = case_key

    async def callback(self, interaction: discord.Interaction):
        view: TicketPanelView = self.view 
        await view.cog.handle_open_ticket(interaction, self.case_key)


class TicketControlsView(discord.ui.View):
    def __init__(self, cog: "BetterTickets", guild_id: int, user_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

        self.add_item(
            TicketCloseButton(
                guild_id=guild_id,
                user_id=user_id,
                cog=cog,
            )
        )


class TicketCloseButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, cog: "BetterTickets"):
        super().__init__(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"bticket:close:{guild_id}:{user_id}",
        )
        self.cog = cog
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.cog.handle_close(interaction, self.user_id)
        except Exception:
            print("Close button error:")
            traceback.print_exc()
            if interaction.response.is_done():
                await interaction.followup.send("An error occurred. Staff: check logs.", ephemeral=True)
            else:
                await interaction.response.send_message("An error occurred. Staff: check logs.", ephemeral=True)



class BetterTickets(commands.Cog):
    """
    Button-based support tickets with additional custom cases.
    """

    __version__ = "2.0.3"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=5465324654986213156, force_registration=False)

        self.config.register_guild(
            panel_channel_id=None,
            panel_message_id=None,
            management_channel_id=None,
            open_category_id=None,
            closed_category_id=None,
            support_role_id=None,
            markasnsfw=False,
            enabled=False,

            cases={},

            case_messages={},

            active={},

            closed=[],
        )

    async def cog_load(self):
        #schedule restore after the bot is actually ready
        if self._restore_task is None or self._restore_task.done():
            self._restore_task = asyncio.create_task(self._restore_views_when_ready())

    async def cog_unload(self):
        if self._restore_task and not self._restore_task.done():
            self._restore_task.cancel()

    async def _restore_views_when_ready(self):
        if hasattr(self.bot, "wait_until_red_ready"):
            await self.bot.wait_until_red_ready()
        else:
            await self.bot.wait_until_ready()

        #on_ready can fire multiple times; prevent double-registration
        if self._views_restored:
            return
        self._views_restored = True

        for guild in self.bot.guilds:
            await self._ensure_panel_view(guild)
            await self._ensure_ticket_views(guild)

    async def _ensure_ticket_views(self, guild: discord.Guild):
        active = await self.config.guild(guild).active()
        for user_id_str, record in list(active.items()):
            ch = guild.get_channel(record.get("channel_id", 0))
            msg_id = record.get("control_msg_id")
            if not isinstance(ch, discord.TextChannel) or not msg_id:
                continue

            # If the message no longer exists, clean stale record
            try:
                await ch.fetch_message(msg_id)
            except discord.NotFound:
                active.pop(user_id_str, None)
                continue
            except discord.Forbidden:
                continue
            except discord.HTTPException:
                continue

            view = TicketControlsView(self, guild.id, int(user_id_str))
            self.bot.add_view(view, message_id=msg_id)

        await self.config.guild(guild).active.set(active)


    async def _ensure_panel_view(self, guild: discord.Guild):
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            return

        channel_id = await self.config.guild(guild).panel_channel_id()
        message_id = await self.config.guild(guild).panel_message_id()
        if not channel_id or not message_id:
            return

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            await channel.fetch_message(message_id)
        except discord.NotFound:
            await self.config.guild(guild).enabled.set(False)
            return
        except discord.Forbidden:
            return

        view = TicketPanelView(self, guild.id)
        await view.rebuild()
        self.bot.add_view(view, message_id=message_id)

    def format_help_for_context(self, ctx: commands.Context) -> str:
        return f"{super().format_help_for_context(ctx)}\n\nVersion: {self.__version__}"

    @commands.group()
    @commands.guild_only()
    @checks.admin()
    @checks.bot_has_permissions(manage_channels=True, manage_messages=True, manage_permissions=True)
    async def tickets(self, ctx: commands.Context):
        """Ticket system configuration."""

    @tickets.command(name="channel")
    async def set_panel_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the ticket request (panel) channel."""
        await self.config.guild(ctx.guild).panel_channel_id.set(channel.id)
        await ctx.send(f"Ticket button channel set to {channel.mention}.")

    @tickets.command(name="management")
    async def set_management_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the support-management log channel."""
        await self.config.guild(ctx.guild).management_channel_id.set(channel.id)
        await ctx.send(f"Management channel set to {channel.mention}.")

    @tickets.command(name="role")
    async def set_support_role(self, ctx: commands.Context, role: discord.Role):
        """Set the support role."""
        await self.config.guild(ctx.guild).support_role_id.set(role.id)
        await ctx.send(f"Support role set to {role.name}.")

    @tickets.group(name="category")
    async def tickets_category(self, ctx: commands.Context):
        """Set open/closed categories."""

    @tickets_category.command(name="open")
    async def set_open_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        await self.config.guild(ctx.guild).open_category_id.set(category.id)
        await ctx.send(f"Open category set to {category.mention}")

    @tickets_category.command(name="closed")
    async def set_closed_category(self, ctx: commands.Context, category: discord.CategoryChannel):
        await self.config.guild(ctx.guild).closed_category_id.set(category.id)
        await ctx.send(f"Closed category set to {category.mention}")

    @tickets.command(name="nsfw")
    async def set_nsfw(self, ctx: commands.Context, enabled: typing.Optional[bool] = None):
        """Mark created tickets as NSFW (true/false)."""
        if enabled is None:
            enabled = not await self.config.guild(ctx.guild).markasnsfw()
        await self.config.guild(ctx.guild).markasnsfw.set(bool(enabled))
        await ctx.send(f"Now marking new tickets as NSFW: {bool(enabled)}")

    @tickets.group(name="case")
    async def tickets_case(self, ctx: commands.Context):
        """Manage ticket cases (button options)."""

    @tickets_case.command(name="add")
    async def case_add(self, ctx: commands.Context, case_key: str, emoji: typing.Optional[typing.Union[discord.Emoji, str]] = None,
        *, title_and_desc: str, ):
        """
        Add a case.

        Usage:
          [p]tickets case add <case_key> [emoji] <title> | <description>

        Example:
          [p]tickets case add rolechange 🧾 Role change | Request a role change
        """
        if "|" not in title_and_desc:
            return await ctx.send("Please format as: `<title> | <description>`")

        title, desc = [x.strip() for x in title_and_desc.split("|", 1)]
        if not title or not desc:
            return await ctx.send("Title/description cannot be empty.")

        if emoji is not None:
            try:
                await ctx.message.add_reaction(emoji)
            except discord.HTTPException:
                return await ctx.send("I can't use that emoji.")

        cases = await self.config.guild(ctx.guild).cases()
        if case_key in cases:
            return await ctx.send("That case_key already exists.")

        cases[case_key] = {"title": title, "desc": desc, "emoji": str(emoji) if emoji else None}
        await self.config.guild(ctx.guild).cases.set(cases)

        try:
            await self.refresh_panel(ctx.guild)
        except TicketError:
            #ignore in this case as we can assume we're mid-setup
            pass

        await ctx.send(f"Added case `{case_key}`: {title}")

    @tickets_case.command(name="del")
    async def case_del(self, ctx: commands.Context, case_key: str):
        cases = await self.config.guild(ctx.guild).cases()
        if case_key not in cases:
            return await ctx.send("No such case_key.")
        cases.pop(case_key, None)
        await self.config.guild(ctx.guild).cases.set(cases)

        case_messages = await self.config.guild(ctx.guild).case_messages()
        case_messages.pop(case_key, None)
        await self.config.guild(ctx.guild).case_messages.set(case_messages)

        await self.refresh_panel(ctx.guild)
        await ctx.send(f"Deleted case `{case_key}`.")

    @tickets_case.command(name="list")
    async def case_list(self, ctx: commands.Context):
        cases = await self.config.guild(ctx.guild).cases()
        if not cases:
            return await ctx.send("No cases configured.")
        lines = []
        for k, v in cases.items():
            e = v.get("emoji") or ""
            lines.append(f"- `{k}` {e} **{v.get('title','')}** - {v.get('desc','')}")
        await ctx.send("\n".join(lines))

    @tickets.command(name="setmsg")
    async def set_case_message(self, ctx: commands.Context, case_key: str, *, message: str):
        """Set custom message shown when a ticket is opened for this case_key."""
        cases = await self.config.guild(ctx.guild).cases()
        if case_key not in cases:
            return await ctx.send("No such case_key.")
        case_messages = await self.config.guild(ctx.guild).case_messages()
        case_messages[case_key] = message
        await self.config.guild(ctx.guild).case_messages.set(case_messages)
        await ctx.send(f"Custom message for `{case_key}` set.")

    @tickets.command(name="delmsg")
    async def del_case_message(self, ctx: commands.Context, case_key: str):
        """Delete the custom message for a support case type using an emoji or title."""
        case_messages = await self.config.guild(ctx.guild).case_messages()
        if case_key not in case_messages:
            return await ctx.send("No custom message set for that case_key.")
        case_messages.pop(case_key, None)
        await self.config.guild(ctx.guild).case_messages.set(case_messages)
        await ctx.send(f"Custom message for `{case_key}` deleted.")

    @tickets.command(name="start")
    async def start(self, ctx: commands.Context):
        """Create / refresh the ticket panel and enable the system."""
        try:
            await self.create_or_update_panel(ctx.guild)
        except TicketError as e:
            return await ctx.send(f"Can't start tickets: {e}")

        await self.config.guild(ctx.guild).enabled.set(True)
        await self._ensure_panel_view(ctx.guild)
        await ctx.tick()

    @tickets.command(name="stop")
    async def stop(self, ctx: commands.Context):
        """Disable and delete the ticket panel message."""
        guild = ctx.guild
        channel_id = await self.config.guild(guild).panel_channel_id()
        message_id = await self.config.guild(guild).panel_message_id()

        if channel_id and message_id:
            ch = guild.get_channel(channel_id)
            if isinstance(ch, discord.TextChannel):
                try:
                    msg = await ch.fetch_message(message_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                except discord.HTTPException:
                    pass

        await self.config.guild(guild).enabled.set(False)
        await self.config.guild(guild).panel_message_id.set(None)
        await ctx.tick()

    @tickets.command(name="settings")
    async def settings(self, ctx: commands.Context):
        """See current settings."""
        data = await self.config.guild(ctx.guild).all()
        embed = discord.Embed(colour=await ctx.embed_colour(), timestamp=utcnow())
        embed.title = "Tickets settings"

        def chan(cid):
            c = ctx.guild.get_channel(cid) if cid else None
            return c.mention if c else "None"

        def cat(cid):
            c = ctx.guild.get_channel(cid) if cid else None
            return c.name if c else "None"

        def role(rid):
            r = ctx.guild.get_role(rid) if rid else None
            return r.name if r else "None"

        embed.add_field(name="Enabled", value=str(bool(data["enabled"])))
        embed.add_field(name="Panel channel", value=chan(data["panel_channel_id"]))
        embed.add_field(name="Management channel", value=chan(data["management_channel_id"]))
        embed.add_field(name="Support role", value=role(data["support_role_id"]))
        embed.add_field(name="Open category", value=cat(data["open_category_id"]))
        embed.add_field(name="Closed category", value=cat(data["closed_category_id"]))
        embed.add_field(name="NSFW tickets", value=str(bool(data["markasnsfw"])))
        embed.add_field(name="Cases", value=str(len(data["cases"])))
        await ctx.send(embed=embed)

    @tickets.command(name="purge")
    async def purge_closed(self, ctx: commands.Context, confirmation: typing.Optional[bool] = None):
        """Delete all closed ticket channels tracked by the bot."""
        if not confirmation:
            return await ctx.send(
                "This will delete **all** tracked closed tickets. This cannot be undone.\n"
                f"Run `{ctx.clean_prefix}tickets purge yes` to confirm."
            )

        closed = await self.config.guild(ctx.guild).closed()
        deleted = 0
        for channel_id in closed[:]:
            ch = ctx.guild.get_channel(channel_id)
            if not ch:
                closed.remove(channel_id)
                continue
            try:
                await ch.delete(reason="Ticket purge")
                deleted += 1
            except discord.HTTPException:
                pass

        await self.config.guild(ctx.guild).closed.set(closed)
        await ctx.send(f"Purged {deleted} closed ticket channels.")

    async def refresh_panel(self, guild: discord.Guild):
        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            return
        await self.create_or_update_panel(guild)
        await self._ensure_panel_view(guild)

    async def create_or_update_panel(self, guild: discord.Guild):
        panel_channel_id = await self.config.guild(guild).panel_channel_id()
        if not panel_channel_id:
            raise TicketError("Panel channel not set.")
        channel = guild.get_channel(panel_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise TicketError("Panel channel invalid.")

        cases = await self.config.guild(guild).cases()
        if not cases:
            raise TicketError("No cases configured.")

        description_lines = ["Click a button below to open a support ticket:\n"]
        for case_key, data in list(cases.items())[:25]:
            emoji = data.get("emoji") or ""
            title = data.get("title") or case_key
            desc = data.get("desc") or ""
            description_lines.append(f"{emoji} **{title}** - {desc}")

        embed = discord.Embed(
            colour=discord.Colour.from_rgb(255, 255, 255),
            title=f"{guild.name} Support Tickets",
            description="\n".join(description_lines),
        )

        message_id = await self.config.guild(guild).panel_message_id()
        view = TicketPanelView(self, guild.id)
        await view.rebuild()

        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
                await msg.edit(embed=embed, view=view)
                return
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

        msg = await channel.send(embed=embed, view=view)
        await self.config.guild(guild).panel_message_id.set(msg.id)

    async def _get_required_settings(self, guild: discord.Guild):
        data = await self.config.guild(guild).all()
        missing = []
        if not data["panel_channel_id"]:
            missing.append("panel channel")
        if not data["management_channel_id"]:
            missing.append("management channel")
        if not data["open_category_id"]:
            missing.append("open category")
        if not data["closed_category_id"]:
            missing.append("closed category")
        if not data["support_role_id"]:
            missing.append("support role")
        if missing:
            raise TicketError("Missing: " + ", ".join(missing))
        return data

    async def handle_open_ticket(self, interaction: discord.Interaction, case_key: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return

        guild = interaction.guild
        user = interaction.user

        enabled = await self.config.guild(guild).enabled()
        if not enabled:
            return await interaction.response.send_message("Tickets are currently disabled.", ephemeral=True)

        try:
            settings = await self._get_required_settings(guild)
        except TicketError as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        cases = await self.config.guild(guild).cases()
        if case_key not in cases:
            return await interaction.response.send_message("That ticket type no longer exists.", ephemeral=True)

        active = await self.config.guild(guild).active()

        #Existing active ticket?
        if str(user.id) in active:
            ch_id = active[str(user.id)].get("channel_id")
            ch = guild.get_channel(ch_id) if ch_id else None
            if isinstance(ch, discord.TextChannel):
                return await interaction.response.send_message(
                    f"You already have an open ticket: {ch.mention}",
                    ephemeral=True,
                )
            #stale record
            active.pop(str(user.id), None)
            await self.config.guild(guild).active.set(active)

        open_category = guild.get_channel(settings["open_category_id"])
        if not isinstance(open_category, discord.CategoryChannel):
            return await interaction.response.send_message("Open category is invalid.", ephemeral=True)

        support_role = guild.get_role(settings["support_role_id"])
        if not support_role:
            return await interaction.response.send_message("Support role is invalid.", ephemeral=True)

        reason_title = cases[case_key].get("title") or case_key
        nsfwYN = bool(settings["markasnsfw"])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True,
            ),
            support_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                read_message_history=True,
            ),
        }

        ticket_channel = await guild.create_text_channel(
            name=f"open-{user.id}",
            overwrites=overwrites,
            category=open_category,
            topic=reason_title,
            nsfw=nsfwYN,
            reason=f"Ticket opened by {user} ({user.id})",
        )

        #Build user-facing message
        case_messages = await self.config.guild(guild).case_messages()
        custom_message = case_messages.get(case_key, "")
        user_message = f"{user.mention}, a staff member will be with you shortly."
        if custom_message:
            user_message += f"\n\n{custom_message}"

        embed = discord.Embed(
            title=reason_title,
            description="Use the button below to close this ticket when it's resolved.",
            timestamp=utcnow(),
        )
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        embed.set_footer(text=f"{user} ({user.id})")

        #Send ticket message ONCE, capture control message id
        controls = TicketControlsView(self, guild.id, user.id)
        control_msg = await ticket_channel.send(content=user_message, embed=embed, view=controls)

        #Create management log message and capture id
        manager_msg_id = 0
        mgmt_channel = guild.get_channel(settings["management_channel_id"])
        if isinstance(mgmt_channel, discord.TextChannel):
            m_embed = discord.Embed(
                title=f"{user} ({user.id})",
                description=reason_title,
                timestamp=utcnow(),
            )
            if user.avatar:
                m_embed.set_thumbnail(url=user.avatar.url)

            manager_msg = await mgmt_channel.send(
                content=f"User: {user.mention}\nChannel: {ticket_channel.mention}",
                embed=m_embed,
            )
            m_embed.set_footer(text=f"Message ID: {manager_msg.id}")
            await manager_msg.edit(embed=m_embed)
            manager_msg_id = manager_msg.id

        #Persist active record ONCE, including control_msg_id
        active[str(user.id)] = {
            "channel_id": ticket_channel.id,
            "manager_msg_id": manager_msg_id,
            "control_msg_id": control_msg.id,
            "case_key": case_key,
        }
        await self.config.guild(guild).active.set(active)

        #Ack interaction
        await interaction.response.send_message(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


    async def handle_close(self, interaction: discord.Interaction, target_user_id: int):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
    
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        staff = interaction.user

        settings = await self.config.guild(guild).all()
        support_role = guild.get_role(settings["support_role_id"]) if settings["support_role_id"] else None
        if not support_role or support_role not in staff.roles:
            return await interaction.followup.send("Only support staff can close tickets.", ephemeral=True)

        active = await self.config.guild(guild).active()
        record = active.get(str(target_user_id))
        if not record:
            return await interaction.followup.send("This ticket is no longer tracked as active.", ephemeral=True)

        if interaction.channel_id != record["channel_id"]:
            return await interaction.followup.send("That close button isn't for this channel.", ephemeral=True)

        ch = guild.get_channel(record["channel_id"])
        closed_category = guild.get_channel(settings["closed_category_id"]) if settings["closed_category_id"] else None
        if not isinstance(ch, discord.TextChannel) or not isinstance(closed_category, discord.CategoryChannel):
            return await interaction.followup.send("Ticket channel/category is invalid.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            support_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                read_message_history=True,
            ),
        }

        try:
            await ch.edit(
                category=closed_category,
                name=f"closed-{target_user_id}",
                overwrites=overwrites,
                reason="Closed support ticket",
            )
        except discord.HTTPException:
            pass

        closed_list = await self.config.guild(guild).closed()
        if ch.id not in closed_list:
            closed_list.append(ch.id)
            await self.config.guild(guild).closed.set(closed_list)

        active.pop(str(target_user_id), None)
        await self.config.guild(guild).active.set(active)

        await self._append_management_state(guild, record.get("manager_msg_id"), "Closed", f"by {staff.mention}")

        await interaction.followup.send("Closed.", ephemeral=True)


    async def _append_management_state(self, guild: discord.Guild, manager_msg_id: int, state: str, text: str):
        if not manager_msg_id:
            return
        mgmt_channel_id = await self.config.guild(guild).management_channel_id()
        ch = guild.get_channel(mgmt_channel_id) if mgmt_channel_id else None
        if not isinstance(ch, discord.TextChannel):
            return
        try:
            msg = await ch.fetch_message(manager_msg_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return
        if not msg.embeds:
            return
        embed = msg.embeds[0]
        when = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(name=state, value=f"{text} at {when}", inline=False)
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass
