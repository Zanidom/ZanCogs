from __future__ import annotations

from typing import Any
import discord
from discord import app_commands, Permissions
from redbot.core import commands, app_commands, Config

from .defaults import DEFAULT_GUILD
from .store import BountyStore
from .services.audit import AuditService
from .services.board import BoardService
from .services.economy import EconomyService
from .util import utcnow_iso
from .ui.embeds import build_bounty_embed
from .ui.modals import EditBountyModal

from .commands import bounty_add, bounty_list, bounty_view, bounty_config, bounty_flow, bounty_help


class Bounties(commands.Cog):
    """Buyer-driven bounties with escrow payouts."""

    bounty = app_commands.Group(name="bounty", description="Create and manage bounties.")
    bountyconfig = app_commands.Group(name="bountyconfig", description="Configure the bounty system.", 
        default_permissions=Permissions(administrator=True),)

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=0xB00B135, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)

        self.store = BountyStore(self.config)
        self.audit = AuditService(bot, self.config)
        self.board = BoardService(bot, self.config)
        self.econ = EconomyService()

    async def cog_load(self):
        bounty_add.register(self.bounty, self)
        bounty_list.register(self.bounty, self)
        bounty_view.register(self.bounty, self)
        bounty_flow.register(self.bounty, self)
        bounty_help.register(self.bounty, self)
        bounty_config.register(self.bountyconfig, self)

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command(self.bounty.name, type=self.bounty.type)
        except Exception:
            pass
        try:
            self.bot.tree.remove_command(self.bountyconfig.name, type=self.bountyconfig.type)
        except Exception:
            pass

    def _embed(self, guild: discord.Guild, bounty: dict[str, Any]) -> discord.Embed:
        return build_bounty_embed(guild, bounty)

    def _is_adminish(self, member: discord.Member) -> bool:
        perms = member.guild_permissions
        return bool(perms.administrator)

    async def _require_owner_or_admin(self, interaction: discord.Interaction, bounty: dict) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return False

        owner_id = int(bounty.get("owner_id", 0))
        actor_id = interaction.user.id

        if actor_id == owner_id:
            return True

        if self._is_adminish(interaction.user):
            return True

        await interaction.response.send_message(
            f"You don't own this bounty. (Owner: <@{owner_id}>)",
            ephemeral=True
        )
        return False

    

    async def _blocked(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return True
        blocked = await self.config.guild(interaction.guild).blocked_user_ids()
        if interaction.user.id in blocked:
            await interaction.response.send_message(
                "You are blocked from using bounty commands on this server.",
                ephemeral=True,
            )
            return True
        return False

    async def _commit(self, guild, bounty, *, audit_text=None):
        await self.store.save(guild, bounty)           
        embed = self._embed(guild, bounty)
        msg_id = await self.board.upsert(guild, bounty, embed=embed) 

        if msg_id and bounty.get("board_message_id") != msg_id:
            bounty["board_message_id"] = msg_id
            await self.store.save(guild, bounty)

        if audit_text:
            await self.audit.log(guild, audit_text)

    async def create_bounty_from_modal(self, interaction: discord.Interaction, *, title: str,
        desc: str, reward: int, max_payouts: int, open_fulfil: bool, ) -> None:
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)

        add_cost = await self.config.guild(interaction.guild).add_cost()
        if add_cost > 0:
            if not await self.econ.can_spend(interaction.user, add_cost):
                await interaction.response.send_message(
                    f"Posting a bounty costs {add_cost}, and you can't afford it.",
                    ephemeral=True,
                )
                return
            await self.econ.withdraw(interaction.user, add_cost)

        if await self.store.title_in_use(interaction.guild, title):
            await interaction.response.send_message(
                "That title is already in use by an active bounty. Please choose a unique title.",
                ephemeral=True,
            )
            return

        bid = await self.store.allocate_id(interaction.guild)

        bounty = {
            "id": bid,
            "title": title.strip(),
            "desc": desc.strip(),
            "reward": int(reward),
            "max_payouts": int(max_payouts),
            "open_fulfil": bool(open_fulfil),

            "owner_id": interaction.user.id,
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),

            "applicants": [],
            "accepted": {},
            "blacklist": [],
            "submissions": {},

            "board_message_id": None,
        }

        await self._commit(interaction.guild, bounty, audit_text=f"Bounty #{bounty['id']} (\"{bounty['title']}\") created by <@{interaction.user.id}>")
        await interaction.response.send_message(embed=self._embed(interaction.guild, bounty))

    async def apply_edit_from_modal(self, interaction: discord.Interaction, bounty_id: int, *, title: str,
        desc: str, reward: int, max_payouts: int, open_fulfil: bool, ) -> None:
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)

        bounty = await self.store.get(interaction.guild, bounty_id)
        if not bounty:
            await interaction.response.send_message("Bounty no longer exists.", ephemeral=True)
            return

        if not await self._require_owner_or_admin(interaction, bounty):
            return

        if await self.store.title_in_use(interaction.guild, title, exclude_id=bounty_id):
            await interaction.response.send_message("That title is already in use by another active bounty.", ephemeral=True)
            return

        if not bounty.get("open_fulfil"):
            accepted = bounty.get("accepted", {}) or {}
            if accepted:
                owner = interaction.guild.get_member(bounty["owner_id"])
                if owner:
                    refund = sum(int(v.get("escrowed", 0)) for v in accepted.values())
                    if refund:
                        await self.econ.deposit(owner, refund)

                for uid in list(accepted.keys()):
                    m = interaction.guild.get_member(int(uid))
                    if m:
                        try:
                            await m.send(f"Bounty #{bounty['id']} - {bounty['title']} was updated; you were unaccepted and escrow was refunded.")
                        except Exception:
                            pass

                bounty["accepted"] = {}
                bounty["applicants"] = []

        bounty["title"] = title.strip()
        bounty["desc"] = desc.strip()
        bounty["reward"] = int(reward)
        bounty["max_payouts"] = int(max_payouts)
        bounty["open_fulfil"] = bool(open_fulfil)

        if bounty["open_fulfil"]:
            bounty["applicants"] = []
            bounty["accepted"] = {}
        else:
            bounty["submissions"] = {}

        await self._commit(interaction.guild, bounty, audit_text=f"Bounty updated by <@{interaction.user.id}>")
        await interaction.response.send_message("Updated:", embed=self._embed(interaction.guild, bounty), ephemeral=False)

    async def _try_dm(self, user: discord.abc.User, content: str) -> bool:
        try:
            await user.send(content)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    @bounty.command(name="edit", description="Edit a bounty by id or exact title (owner/admin).")
    @app_commands.guild_only()
    async def bounty_edit(self, interaction: discord.Interaction, key: str):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if await self._blocked(interaction):
            return

        bounty = await self.store.find_by_key(interaction.guild, key)
        if not bounty:
            await interaction.response.send_message("Bounty not found.", ephemeral=True)
            return

        if not await self._require_owner_or_admin(interaction, bounty):
            return

        await interaction.response.send_modal(EditBountyModal(self, bounty_id=bounty["id"], seed=bounty))
