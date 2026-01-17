import asyncio
import datetime
import time
import io
from typing import Dict, List, Tuple, Optional

import discord
from discord import app_commands, Permissions
from discord.utils import get
from redbot.core import commands
from redbot.core import checks, Config, bank, modlog, commands

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    Image = None    
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False


def human_timedelta(seconds: int) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


class Kotr(commands.Cog):
    """
    KotR - King of the Role v2,
    now with more interactive everything!
    """

    def __init__(self, bot):
        self.bot = bot
        self.version = "b1.1"
        self.redver = "3.3.9"
        self.config = Config.get_conf(self, identifier=6942069, force_registration=True)
        default_guild = {
            "Config": {
                "Cost": 100,
                "MinCost": 100,
                "Increase": 100,
                "Decrease": 5,
                "Timer": 300,
                "LastPurchase": 0,
                "LastPaid": 0,
                "Cooldown": 600,
                "Registered": False,
                "RecentlyStarted": False,
            },
            "OwnerInfo": {"Owner": 1},
            "RoleInfo": {"Role": "", "RoleId": 0},
            "Colours": {
                "Light Blue": 0xAAE2FF,
                "Blue": 0x5479FF,
                "Dark Blue": 0x2D4189,
                "Light Red": 0xFF6D79,
                "Red": 0xFF2335,
                "Dark Red": 0xAD1824,
                "Light Pink": 0xFF84E2,
                "Dark Pink": 0xAD0580,
                "Light Orange": 0xFF9359,
                "Orange": 0xFF5400,
                "Dark Orange": 0xC43E00,
                "Brown": 0x824024,
                "Light Purple": 0x7F00C9,
                "Dark Purple": 0x580082,
                "White": 0xFFFFFF,
            },
            "RoleTitles": {
                "King of the Role": 0,
                "Queen of the Role": 0,
                "Role Monarch": 0,
                "Brat King": 0,
                "Brat Queen": 0,
                "Brat Monarch": 0,
                "Role Champion": 0,
                "Awesome Being": 0,
                "Rich Kid": 0,
                "Zanillionaire": 0,
            },
            "RoleIcons": ["👑", "✨", "🔥", "⭐", "💎", "⚡", "🌈"],
            "UserStats": {},	 
        }
        self.config.register_guild(**default_guild)

    async def _ensure_user_stats(self, guild: discord.Guild, uid: int) -> dict:
        """Ensure a stats record exists for a user; return it."""
        stats = await self.config.guild(guild).UserStats()
        key = str(uid)
        if key not in stats:
            stats[key] = {
                "holdTimes": [],
                "totalHoldTime": 0,
                "preferredIcon": None,
                "preferredColour": None,
                "preferredTitle": None,
            }
            await self.config.guild(guild).UserStats.set(stats)
        return stats[key]

    async def _save_user_stats(self, guild: discord.Guild, uid: int, data: dict) -> None:
        stats = await self.config.guild(guild).UserStats()
        stats[str(uid)] = data
        await self.config.guild(guild).UserStats.set(stats)

    async def _close_current_owner_slot(self, guild: discord.Guild, when: Optional[int] = None) -> None:
        """End the current owner's active holding window, if any, and add to total."""
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        owner_id = ownerInfo.get("Owner")
        if not owner_id or owner_id == 1:
            return
        stats = await self._ensure_user_stats(guild, owner_id)
        now = int(when or time.time())
        updated = False
        for slot in stats["holdTimes"]:
            if int(slot.get("endTime", 0) or 0) == 0:
                slot["endTime"] = now
                delta = max(0, now - int(slot.get("startTime", now)))
                stats["totalHoldTime"] = int(stats.get("totalHoldTime", 0)) + delta
                updated = True
                break
        if updated:
            await self._save_user_stats(guild, owner_id, stats)

    async def _open_new_owner_slot(self, guild: discord.Guild, uid: int, when: Optional[int] = None) -> None:
        stats = await self._ensure_user_stats(guild, uid)
        now = int(when or time.time())
        stats["holdTimes"].append({"startTime": now, "endTime": 0})
        await self._save_user_stats(guild, uid, stats)

    async def _current_cost(self, guild: discord.Guild) -> int:
        cfg = await self.config.guild(guild).Config()
        curTime = int(time.time())
        timeDif = curTime - cfg["LastPurchase"]
        cost = cfg["Cost"] - int((timeDif / cfg["Timer"])) * cfg["Decrease"]
        return max(cost, cfg["MinCost"])

    @staticmethod
    def _draw_check_swatch(rgb: Tuple[int, int, int], size: int = 64) -> io.BytesIO:
        fp = io.BytesIO()

        if not PIL_AVAILABLE:
            fp.write(b"")
            fp.seek(0)
            return fp

        img = Image.new("RGBA", (size, size), rgb + (255,))
        draw = ImageDraw.Draw(img)
        w = size
        draw.line([(w * 0.2, w * 0.55), (w * 0.45, w * 0.8)], fill=(255, 255, 255, 255), width=max(2, size // 12))
        draw.line([(w * 0.45, w * 0.8), (w * 0.8, w * 0.25)], fill=(255, 255, 255, 255), width=max(2, size // 12))
        img.save(fp, format="PNG")
        fp.seek(0)
        return fp


    @staticmethod
    def _render_username_preview(username: str, rgb: Tuple[int, int, int]) -> io.BytesIO:
        fp = io.BytesIO()

        if not PIL_AVAILABLE:
            fp.write(b"")
            fp.seek(0)
            return fp

        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
        except Exception:
            font = ImageFont.load_default()

        try:
            left, top, right, bottom = font.getbbox(username)
            w = right - left
            h = bottom - top
        except Exception:
            tmp = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            draw = ImageDraw.Draw(tmp)
            bbox = draw.textbbox((0, 0), username, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]

        pad = 20
        img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            left, top, _, _ = font.getbbox(username)
        except Exception:
            left, top = 0, 0

        draw.text((pad - left, pad - top), username, font=font, fill=rgb + (255,))

        img.save(fp, format="PNG")
        fp.seek(0)
        return fp


    @commands.hybrid_group(name="kotr", with_app_command=True)
    async def kotr(self, ctx):
        """King of the Role commands"""
        pass

    @kotr.command(name="owner")
    async def _info_kotr(self, ctx):
        """Shows info about the current role owner."""
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        ownerId = ownerInfo["Owner"]

        try:
            ownerUser = await self.bot.fetch_user(ownerId)
        except Exception:
            await ctx.send("Error looking up user. The role may not have been bought yet.")
            return

        avatar = getattr(ownerUser, "display_avatar", None) or ownerUser.avatar_url
        embed = discord.Embed(colour=0x0066FF, description="\n")
        embed.title = f"{guild.name} current KotR settings:"
        embed.set_thumbnail(url=str(avatar))
        embed.add_field(name="Current KotR owner", value=ownerUser.display_name)
        embed.add_field(
            name="Currently owned since",
            value=datetime.datetime.fromtimestamp(serverConfig["LastPurchase"]).strftime("%Y-%m-%d %H:%M:%S"),
        )
        embed.add_field(name="Bought for", value=serverConfig["LastPaid"])
        await ctx.send(embed=embed)

    @kotr.command(name="config")
    async def _config_kotr(self, ctx):
        """Shows the Kotr configuration for this server."""
        guild = ctx.guild
        await self.check_server_settings(guild)
        serverConfig = await self.config.guild(guild).Config()
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        roleInfo = await self.config.guild(guild).RoleInfo()
        ownerId = ownerInfo["Owner"]
        role = ctx.guild.get_role(roleInfo["RoleId"])
        if role is None:
            role = "Invalid role configuration."

        try:
            ownerUser = await self.bot.fetch_user(ownerId)
        except Exception:
            ownerUser = "Not yet owned."
        cost = await self._current_cost(guild)

        embed = discord.Embed(colour=0x0066FF, description="\n")
        embed.title = f"{guild.name} KotR settings:"
        embed.add_field(name="KotR cost", value=cost)
        embed.add_field(name="Minimum cost:", value=serverConfig["MinCost"])
        embed.add_field(name="Increase on purchase", value=serverConfig["Increase"])
        embed.add_field(name="Decrease per tick:", value=serverConfig["Decrease"])
        embed.add_field(name="Time per tick:", value=serverConfig["Timer"])
        embed.add_field(name="Cooldown between purchases:", value=serverConfig["Cooldown"])
        embed.add_field(name="Current Owner:", value=ownerUser)
															   
        embed.add_field(name="Role:", value=role)
        await ctx.send(embed=embed)

    class ConfirmView(discord.ui.View):
        def __init__(self, author: discord.abc.User, timeout: int = 60):
            super().__init__(timeout=timeout)
            self.author = author
            self.value: Optional[bool] = None
            self.interaction: Optional[discord.Interaction] = None

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("This confirmation isn't for you.", ephemeral=True)
                return False
            return True

        @discord.ui.button(emoji="✅", style=discord.ButtonStyle.success)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = True
            self.interaction = interaction
            await interaction.response.send_message("Confirmed.", ephemeral=True)
            self.stop()

        @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.value = False
            self.interaction = interaction
            await interaction.response.send_message("Cancelled.", ephemeral=True)
            self.stop()

        async def on_timeout(self) -> None:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

    @kotr.command(name="buyrole")
    async def _buy_kotrRole(self, ctx):
        """Makes you the shiny new owner of the KotR role!"""
        config = await self.config.guild(ctx.guild).Config()
        author = ctx.author
        costIncrease = config["Increase"]
        curBal = await bank.get_balance(ctx.author)
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = ctx.guild.get_role(roleInfo["RoleId"])

        if author.id == ownerInfo["Owner"]:
            await ctx.send("You already own the role!")
            return

        curTime = int(time.time())
        timeDif = curTime - config["LastPurchase"]
        cost = await self._current_cost(ctx.guild)

        if timeDif < config["Cooldown"]:
            await ctx.send(f"It's too soon! Buying this role is still on cooldown for another ~{config['Cooldown'] - timeDif} seconds.")
            return

        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return

        if not curBal >= cost:
            await ctx.send(f"You don't have enough credits to buy the role!\nYou have {curBal} and it currently costs {cost}.")
            return

        embed = discord.Embed(
            title="Confirm Purchase",
            description=f"You have **{curBal}** credits.\nThis role currently costs **{cost}**.\nProceed?",
            colour=discord.Colour.green()
        )

        view = self.ConfirmView(author=author, timeout=45)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        
        try:
            await msg.delete()
        except Exception:
            pass
        
        if view.value is not True:
            await ctx.send("Purchase not confirmed.")
            return

        try:
            oldOwner = ctx.guild.get_member(ownerInfo["Owner"])
        except Exception:
            oldOwner = None
        await self._close_current_owner_slot(ctx.guild, when=curTime)
        ownerInfo["Owner"] = author.id
        await bank.withdraw_credits(author, cost)
        try:
            if oldOwner:
                await oldOwner.remove_roles(role, reason="KotR sold to another user")
            await author.add_roles(role, reason="KotR purchase")
        except Exception:
            await ctx.send("Something went wrong - possible permissions issue. Exiting procedure.")
            return
        
        newCost = cost + costIncrease
        await ctx.send(f"Purchase successful - congrats! New price: {newCost}")
        config["Cost"] = newCost
        config["LastPurchase"] = curTime
        config["LastPaid"] = cost
        await self.config.guild(ctx.guild).Config.set(config)
        await self.config.guild(ctx.guild).OwnerInfo.set(ownerInfo)
        await self._open_new_owner_slot(ctx.guild, author.id, when=curTime)

    class _PagedView(discord.ui.View):
        def __init__(self, cog: "Kotr", ctx: commands.Context, items: List, per_page: int = 3, timeout: int = 60, *, ephemeral: bool = False):
            super().__init__(timeout=timeout)
            self.cog = cog
            self.ctx = ctx
            self.items = items
            self.per_page = per_page
            self.page = 0
            self.ephemeral = ephemeral
            self.message: Optional[discord.Message] = None
            self.preview_message: Optional[discord.Message] = None

        def _slice(self) -> List:
            start = self.page * self.per_page
            return self.items[start : start + self.per_page]

        def _page_count(self) -> int:
            return max(1, (len(self.items) + self.per_page - 1) // self.per_page)

        async def _refresh(self, interaction: Optional[discord.Interaction] = None):
            raise NotImplementedError

        async def _on_prev(self, interaction: discord.Interaction):
            await interaction.response.defer()
            if self.page > 0:
                self.page -= 1
                await self._refresh()

        async def _on_next(self, interaction: discord.Interaction):
            await interaction.response.defer()
            if (self.page + 1) * self.per_page < len(self.items):
                self.page += 1
                await self._refresh()

        def _nav_buttons(self) -> Tuple[discord.ui.Button, discord.ui.Button]:
            b_prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, row=2)
            b_next = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, row=2)
            b_prev.callback = self._on_prev
            b_next.callback = self._on_next
            b_prev.disabled = (self.page <= 0)
            b_next.disabled = ((self.page + 1) * self.per_page >= len(self.items))
            return b_prev, b_next

        async def _ensure_main_message(self, content: str, *, view: "discord.ui.View"):
            if self.message is None:
                if self.ephemeral and getattr(self.ctx, "interaction", None):
                    inter = self.ctx.interaction
                    await inter.response.send_message(content=content, view=view, ephemeral=True)
                    self.message = await inter.original_response()
                else:
                    self.message = await self.ctx.send(content=content, view=view)
                return

            await self.message.edit(content=content, view=view)

        async def _send_or_replace_preview(self, interaction: Optional[discord.Interaction], *, files: List[discord.File], content: Optional[str] = None):
            if not files:
                return

            if not self.ephemeral or interaction is None:
                if self.preview_message:
                    try:
                        await self.preview_message.delete()
                    except Exception:
                        pass
                self.preview_message = await self.ctx.send(content=content, files=files)
                return

            if self.preview_message:
                try:
                    await self.preview_message.delete()
                except Exception:
                    self.preview_message = None

            self.preview_message = await interaction.followup.send(content=content, files=files, ephemeral=True, wait=True)

        async def _cleanup_ui(self):
            if self.message:
                try:
                    await self.message.edit(view=None)
                except Exception:
                    pass

            if self.preview_message:
                try:
                    await self.preview_message.delete()
                except Exception:
                    pass

            self.stop()

        async def on_timeout(self) -> None:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            if self.message:
                try:
                    await self.message.edit(view=self)
                except Exception:
                    pass


    class ColourPickerView(_PagedView):
        def __init__(self, cog: "Kotr", ctx: commands.Context, options: List[Tuple[str, int]], role: discord.Role, *, ephemeral: bool):
            super().__init__(cog, ctx, options, per_page=3, timeout=90, ephemeral=ephemeral)
            self.role = role

        async def _refresh(self, interaction: Optional[discord.Interaction] = None):
            self.clear_items()
            slice_items = self._slice()

            for name, val in slice_items:
                hexval = f"#{val:06X}"
                btn = discord.ui.Button(label=f"{name} ({hexval})", style=discord.ButtonStyle.primary, emoji="🎨")

                async def _cb(inter: discord.Interaction, v=val, n=name):
                    await inter.response.defer()
                    try:
                        await self.role.edit(colour=v)
                        stats = await self.cog._ensure_user_stats(self.ctx.guild, self.ctx.author.id)
                        stats["preferredColour"] = int(v)
                        await self.cog._save_user_stats(self.ctx.guild, self.ctx.author.id, stats)
                        await inter.followup.send(f"Colour set to **{n}**.", ephemeral=True)
                        await self._cleanup_ui()
                    except Exception:
                        await inter.followup.send("Couldn't change colour (missing permissions or invalid role).", ephemeral=True)

                btn.callback = _cb
                self.add_item(btn)

            b_prev, b_next = self._nav_buttons()
            self.add_item(b_prev)
            self.add_item(b_next)

            content = f"Pick a colour - Page {self.page + 1}/{self._page_count()}"
            await self._ensure_main_message(content, view=self)

            files: List[discord.File] = []
            if PIL_AVAILABLE:
                for idx, (_, val) in enumerate(slice_items, start=1):
                    r = (val >> 16) & 255
                    g = (val >> 8) & 255
                    b = val & 255
                    img = self.cog._render_username_preview(self.ctx.author.display_name, (r, g, b))
                    files.append(discord.File(img, filename=f"preview_{idx}.png"))

            if files:
                await self._send_or_replace_preview(interaction, files=files)



    class ColourPreviewView(_PagedView):
        """For ;kotr colourlist, paginate previews without selection buttons."""
        def __init__(self, cog: "Kotr", ctx: commands.Context, options: List[Tuple[str, int]], *, ephemeral: bool):
            super().__init__(cog, ctx, options, per_page=3, timeout=90, ephemeral=ephemeral)

        async def _refresh(self, interaction: Optional[discord.Interaction] = None):
            self.clear_items()
            slice_items = self._slice()
    
            b_prev, b_next = self._nav_buttons()
            self.add_item(b_prev)
            self.add_item(b_next)

            page_title = f"Available colours - Page {self.page + 1}/{self._page_count()}"
            embed = discord.Embed(title=page_title, colour=discord.Colour.blurple())
            embed.description = "\n".join([f"**{n}** - `#{v:06X}`" for n, v in slice_items]) or "No colours configured."

            if self.message is None:
                if self.ephemeral and getattr(self.ctx, "interaction", None):
                    inter = self.ctx.interaction
                    await inter.response.send_message(embed=embed, view=self, ephemeral=True)
                    self.message = await inter.original_response()
                else:
                    self.message = await self.ctx.send(embed=embed, view=self)
            else:
                await self.message.edit(embed=embed, view=self)

            files: List[discord.File] = []
            if PIL_AVAILABLE:
                for idx, (name, val) in enumerate(slice_items, start=1):
                    r = (val >> 16) & 255
                    g = (val >> 8) & 255
                    b = val & 255
                    img = self.cog._render_username_preview(self.ctx.author.display_name, (r, g, b))
                    files.append(discord.File(img, filename=f"{name}_preview_{idx}.png"))

            if files:
                await self._send_or_replace_preview(interaction, files=files)



    class TitlePickerView(_PagedView):
        def __init__(self, cog: "Kotr", ctx: commands.Context, options: List[str], role: discord.Role, *, ephemeral: bool):
            super().__init__(cog, ctx, options, per_page=3, timeout=90, ephemeral=ephemeral)
            self.role = role

        async def _refresh(self, interaction: Optional[discord.Interaction] = None):
            self.clear_items()
            slice_items = self._slice()

            for title in slice_items:
                btn = discord.ui.Button(label=title, style=discord.ButtonStyle.primary)

                async def _cb(inter: discord.Interaction, t=title):
                    await inter.response.defer()
                    try:
                        await self.role.edit(name=t)
                        stats = await self.cog._ensure_user_stats(self.ctx.guild, self.ctx.author.id)
                        stats["preferredTitle"] = t
                        await self.cog._save_user_stats(self.ctx.guild, self.ctx.author.id, stats)
                        await inter.followup.send(f"Title set to **{t}**.", ephemeral=True)
                        await self._cleanup_ui()
                    except Exception:
                        await inter.followup.send("Couldn't change title (missing permissions or invalid role).", ephemeral=True)

                btn.callback = _cb
                self.add_item(btn)

            b_prev, b_next = self._nav_buttons()
            self.add_item(b_prev)
            self.add_item(b_next)

            content = f"Pick a title - Page {self.page + 1}/{self._page_count()}"
            await self._ensure_main_message(content, view=self)


    class IconPickerView(_PagedView):
        def __init__(self, cog: "Kotr", ctx: commands.Context, options: List[str], role: discord.Role, *, ephemeral: bool):
            super().__init__(cog, ctx, options, per_page=3, timeout=90, ephemeral=ephemeral)
            self.role = role

        async def _refresh(self, interaction: Optional[discord.Interaction] = None):
            self.clear_items()
            slice_items = self._slice()

            for icon in slice_items:
                btn = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=icon if len(icon) <= 2 else None,
                )

                async def _cb(inter: discord.Interaction, i=icon):
                    await inter.response.defer()
                    try:
                        await self.role.edit(unicode_emoji=i)
                        stats = await self.cog._ensure_user_stats(self.ctx.guild, self.ctx.author.id)
                        stats["preferredIcon"] = i
                        await self.cog._save_user_stats(self.ctx.guild, self.ctx.author.id, stats)
                        await inter.followup.send(f"Icon set to {i}", ephemeral=True)
                        await self._cleanup_ui()
                    except Exception:
                        await inter.followup.send(
                            "Couldn't change icon. Your server might not support role icons (Requires Server Boost Lv. 2) or I lack permissions.",
                            ephemeral=True,
                        )

                btn.callback = _cb
                self.add_item(btn)

            b_prev, b_next = self._nav_buttons()
            self.add_item(b_prev)
            self.add_item(b_next)

            content = f"Pick an icon - Page {self.page + 1}/{self._page_count()}"
            await self._ensure_main_message(content, view=self)

    @kotr.command(name="setcolour")
    async def _set_kotrColour(self, ctx: commands.Context):
        """If you're the owner, pick your colour!"""
        author = ctx.author
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        if author.id != ownerInfo["Owner"]:
            await ctx.send("You don't own the role currently!\nOnly the owner of the role may set their colour.")
            return

        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = ctx.guild.get_role(roleInfo["RoleId"])
        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return

        colourList = await self.config.guild(ctx.guild).Colours()
        items = [(k, colourList[k]) for k in sorted(colourList.keys())]

        ephemeral = ctx.interaction is not None
        view = self.ColourPickerView(self, ctx, items, role, ephemeral=ephemeral)
    
        await view._refresh()


    @kotr.command(name="setcolor", hidden=True)
    async def _set_kotrColor(self, ctx):
        await self._set_kotrColour(ctx)

    @kotr.command(name="settitle")
    async def _set_kotrtitle(self, ctx: commands.Context):
        """If you're the owner, pick your role's title."""			
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        if ctx.author.id != ownerInfo["Owner"]:
            await ctx.send("You don't own the role currently!\nOnly the owner may set the title.")
            return

        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = ctx.guild.get_role(roleInfo["RoleId"])
        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return

        titleList = await self.config.guild(ctx.guild).RoleTitles()
        items = list(sorted(titleList.keys()))

        ephemeral = ctx.interaction is not None
        view = self.TitlePickerView(self, ctx, items, role, ephemeral=ephemeral)
        await view._refresh()


    @kotr.command(name="seticon")
    async def _set_kotr_icon(self, ctx: commands.Context):
        """If you're the owner, pick your role's icon from presets."""
        ownerInfo = await self.config.guild(ctx.guild).OwnerInfo()
        if ctx.author.id != ownerInfo["Owner"]:
            await ctx.send("You don't own the role currently!\nOnly the owner may set the icon.")
            return

        roleInfo = await self.config.guild(ctx.guild).RoleInfo()
        role = ctx.guild.get_role(roleInfo["RoleId"])
        if role is None:
            await ctx.send("Error looking up role. The role may not have been configured.")
            return

        icons = await self.config.guild(ctx.guild).RoleIcons()
        if not icons:
            await ctx.send("No icon presets configured yet.")
            return

        ephemeral = ctx.interaction is not None
        view = self.IconPickerView(self, ctx, icons, role, ephemeral=ephemeral)
        await view._refresh()


    @kotr.command(name="scoreboard")
    async def _scoreboard(self, ctx, top: int = 10):
        """Show the longest total ownerships in this server."""
        guild = ctx.guild
        stats: Dict[str, dict] = await self.config.guild(guild).UserStats()
        ownerInfo = await self.config.guild(guild).OwnerInfo()
        now = int(time.time())
        totals: List[Tuple[int, int]] = []
        for uid_str, data in stats.items():
            total = int(data.get("totalHoldTime", 0))
            for slot in data.get("holdTimes", []):
                st = int(slot.get("startTime", 0))
                et = int(slot.get("endTime", 0) or 0)
                if et == 0 and int(uid_str) == ownerInfo.get("Owner"):
                    total += max(0, now - st)
            totals.append((int(uid_str), total))

        cur_owner = ownerInfo.get("Owner")
        if cur_owner and str(cur_owner) not in stats:
            cfg = await self.config.guild(guild).Config()
            started = int(cfg.get("LastPurchase", now))
            totals.append((int(cur_owner), max(0, now - started)))

        totals.sort(key=lambda t: t[1], reverse=True)
        top = max(1, min(25, top))
        lines = []
        for idx, (uid, seconds) in enumerate(totals[:top], start=1):
            member = guild.get_member(uid) or await self.bot.fetch_user(uid)
            name = getattr(member, "display_name", getattr(member, "name", str(uid)))
            lines.append(f"**{idx}.** {name} - {human_timedelta(seconds)}")

        if not lines:
            await ctx.send("No ownership data yet.")
            return

        embed = discord.Embed(title=f"{guild.name} - KotR Scoreboard (Top {top})", colour=0x0066FF)
        embed.description = "\n".join(lines)
        await ctx.send(embed=embed)

    @kotr.command(name="cost")
    async def _get_kotrCostr(self, ctx):
        """Get the current cost of the role."""
        cost = await self._current_cost(ctx.guild)					
        await ctx.send(f"The role currently costs {cost}.")

    @kotr.command(name="colourlist")
    async def _get_colours(self, ctx: commands.Context):
        """Shows previews of all configured colours on the server (paginated)."""
        colourList = await self.config.guild(ctx.guild).Colours()
        items = [(k, colourList[k]) for k in sorted(colourList.keys())]

        ephemeral = ctx.interaction is not None
        view = self.ColourPreviewView(self, ctx, items, ephemeral=ephemeral)
        await view._refresh()


    @kotr.command(name="colorlist", hidden=True)
    async def _get_colors(self, ctx):
        await self._get_colours(ctx)

    @kotr.command(name="titlelist")
    async def _get_titles(self, ctx):
        """Shows a list of all configured titles on the server."""
        titleList = await self.config.guild(ctx.guild).RoleTitles()
        titleList = sorted(titleList)

        embed = discord.Embed(title="Available titles", colour=discord.Colour.blurple())
        embed.description = "\n".join(f"- {t}" for t in titleList) or "None configured." 
        await ctx.send(embed=embed)

    @commands.group(no_pm=True, pass_context=True)
    async def setkotr(self, ctx):
        """Set config options for KotR"""
        pass

    @setkotr.command(name="role", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrrole(self, ctx, roleName: str):
        """Set the role to be used by KotR."""
        guild = ctx.guild
        roleInfo = await self.config.guild(guild).RoleInfo()
        if "<@&" in roleName:
            role = guild.get_role(int(roleName[3:-1]))
        else:
            role = get(guild.roles, name=roleName)
        if role is None:
            await ctx.send(f"Couldn't find a role with the name {roleName}. Exiting.")
            return

        roleInfo["RoleId"] = role.id
        await self.config.guild(ctx.guild).RoleInfo.set(roleInfo)
        await ctx.send(f"Command succeeded. New role: {role.mention} (id {role.id})")

    @setkotr.command(name="cost", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrcost(self, ctx, newCost: int):
        """Set the current cost of the role."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()

        curTime = int(time.time())
        timeDif = curTime - config["LastPurchase"]
        currentDiscount = int((timeDif / config["Timer"])) * config["Decrease"]
        config["Cost"] = newCost + currentDiscount

        await ctx.send(f"Command succeeded. New price: {newCost}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="mincost", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrmincost(self, ctx, newCost: int):
        """Set the minimum cost of the role."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["MinCost"] = newCost
        await ctx.send(f"Command succeeded. New minimum cost: {newCost}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="increase", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrincrease(self, ctx, newIncrease: int):
        """Set how much the cost increases when purchased."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Increase"] = newIncrease
        await ctx.send(f"Command succeeded. New increase on purchase: {newIncrease}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="decrease", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrdecrease(self, ctx, newDecrease: int):
        """Set how much the price decreases by each tick."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Decrease"] = newDecrease
        await ctx.send(f"Command succeeded. New decrease each tick: {newDecrease}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="timer", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrtimer(self, ctx, newTimer: int):
        """Set the time between ticks."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Timer"] = newTimer
        await ctx.send(f"Command succeeded. New time between ticks: {newTimer}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="cooldown", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_setkotrcooldown(self, ctx, newCooldown: int):
        """Set the cooldown between the role being bought."""
        guild = ctx.guild
        config = await self.config.guild(guild).Config()
        config["Cooldown"] = newCooldown
        await ctx.send(f"Command succeeded. New cooldown prior to more purchases: {newCooldown}")
        await self.config.guild(guild).Config.set(config)

    @setkotr.command(name="addcolour", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_addcolour(self, ctx):
        """Add a colour to the list."""
        colourList = await self.config.guild(ctx.guild).Colours()
        check = lambda m: m.author == ctx.author

        await ctx.send("Please input your new colour name.")
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        if response.content.title() in colourList:
            await ctx.send("That colour name already exists - overwriting.")

        newColourName = response.content.title()
        await ctx.send("What colour value? (Formats: 0x123456, #123456, or 123456)")
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return
        try:
            s = response.content.strip().lower()
            if s.startswith("0x"):
                newColour = int(s[2:], 16)
            elif s.startswith("#"):							 
                newColour = int(s[1:], 16)																			  
            else:
                newColour = int(s, 16)
																 
        except Exception:
            await ctx.send("Could not parse your input, cancelling.")
            return

        colourList[newColourName] = newColour
        await ctx.send(f"Added **{newColourName}** with value **{newColour:06X}**.")
        await self.config.guild(ctx.guild).Colours.set(colourList)

    @setkotr.command(name="removecolour", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_removecolour(self, ctx):
        """Removes a colour from the list (with confirmation buttons)."""
        colourList = await self.config.guild(ctx.guild).Colours()
        check = lambda m: m.author == ctx.author

        await ctx.send("Please input the colour you want to delete.")
        try:
            colourNameMSG = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        colourName = colourNameMSG.content.title()
        if colourName not in colourList:
            await ctx.send("No colour with that name found. Exiting.")
            return
		
        colourVal = colourList[colourName]
        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"Delete **{colourName}** (`#{colourVal:06X}`)?",
            colour=discord.Colour.red()
        )
        view = self.ConfirmView(author=ctx.author, timeout=45)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        try:
            await msg.edit(view=view)
        except Exception:
            pass
				  
        if view.value is not True:
            await ctx.send("Deletion cancelled.")
            return
																														
        del colourList[colourName]
        await self.config.guild(ctx.guild).Colours.set(colourList)

        await ctx.send(f"Deleted {colourName}.")

    @setkotr.command(name="addtitle", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_addtitle(self, ctx):
        """Add a title to the list."""
        titleList = await self.config.guild(ctx.guild).RoleTitles()
        check = lambda m: m.author == ctx.author

		
        await ctx.send("Please input your new title.")
        try:
            response = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        newTitleName = response.content.title()
        if newTitleName in titleList:
            await ctx.send("That title already exists.")
            return

        titleList[newTitleName] = 0
        await ctx.send(f"Successfully added new title \"{newTitleName}\".")
        await self.config.guild(ctx.guild).RoleTitles.set(titleList)

    @setkotr.command(name="removetitle", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _output_removetitle(self, ctx):
        """Removes a title from the list (with confirmation buttons)."""
        titleList = await self.config.guild(ctx.guild).RoleTitles()
        check = lambda m: m.author == ctx.author

        await ctx.send("Please input the title you want to delete.")
        try:
            titleNameMSG = await self.bot.wait_for("message", timeout=30, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Cancelled, you took too long.")
            return

        titleName = titleNameMSG.content.title()
        if titleName not in titleList:
            await ctx.send("No title with that name found. Exiting.")
            return

        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"Delete title \"{titleName}\"?",
            colour=discord.Colour.red()
        )
        view = self.ConfirmView(author=ctx.author, timeout=45)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        if view.value is not True:
            await ctx.send("Deletion cancelled.")
            return

        del titleList[titleName]
        await self.config.guild(ctx.guild).RoleTitles.set(titleList)
        await ctx.send(f"Successfully deleted \"{titleName}\" from the title list.")

    @setkotr.command(name="addicon", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _add_icon_preset(self, ctx, *, emoji_or_char: str):
        """Add an icon (unicode emoji recommended) to the preset list for owners to choose from."""
        icons = await self.config.guild(ctx.guild).RoleIcons()
        emoji_or_char = emoji_or_char.strip()
        if emoji_or_char in icons:
            await ctx.send("That icon is already in the list.")
            return
        icons.append(emoji_or_char)
        await self.config.guild(ctx.guild).RoleIcons.set(icons)
        await ctx.send(f"Added icon preset: {emoji_or_char}")

    @setkotr.command(name="removeicon", pass_context=True)
    @checks.admin_or_permissions(manage_guild=True)
    async def _remove_icon_preset(self, ctx, *, emoji_or_char: str):
        """Remove an icon from the preset list (with confirmation buttons)."""
        icons = await self.config.guild(ctx.guild).RoleIcons()
        emoji_or_char = emoji_or_char.strip()
        if emoji_or_char not in icons:
            await ctx.send("That icon isn't in the list.")
            return

        embed = discord.Embed(
            title="Confirm Deletion",
            description=f"Remove icon preset {emoji_or_char}?",
            colour=discord.Colour.red()
        )
        view = self.ConfirmView(author=ctx.author, timeout=45)
        msg = await ctx.send(embed=embed, view=view)
        await view.wait()
        try:
            await msg.edit(view=view)
        except Exception:
            pass

        if view.value is not True:
            await ctx.send("Deletion cancelled.")
            return

        icons.remove(emoji_or_char)
        await self.config.guild(ctx.guild).RoleIcons.set(icons)
        await ctx.send(f"Removed icon preset: {emoji_or_char}")

    async def check_server_settings(self, guild):
        cur = await self.config.guild(guild).Config()
        if not cur["Registered"]:
            cur["Registered"] = True
            await self.config.guild(guild).Config.set(cur)
