from __future__ import annotations

import random
from typing import Any, Optional

import discord
from discord import app_commands

from redbot.core import commands, Config
from redbot.core.bot import Red

from .constants import CONFIG_IDENTIFIER, MAX_LIST_LINES_PER_PAGE, MAX_ROLLS, WEIGHT_MAX, PAGINATOR_TIMEOUT
from .ui.paginator import EmbedPaginator
from .ui.modals import PunishmentModal, RuleModal


class Punishments(commands.Cog):
    """Cog for managing your own punishment table & chat rules."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=CONFIG_IDENTIFIER, force_registration=True)

        self.config.register_member( 
            punishments=[],
            rules=[],
            next_punishment_id=1,
            next_rule_id=1
        )

        self.punishment_group = app_commands.Group(name="punishment", description="Manage personal punishments and rules.")
        self.rules_group = app_commands.Group(name="rules", description="Manage personal chat rules.", parent=self.punishment_group)
        self.admin_group = app_commands.Group(name="admin", description="Admin tools for managing other users' tables.", parent=self.punishment_group)

        self._build_app_commands()

    async def cog_load(self):
        self.bot.tree.add_command(self.punishment_group)

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command(self.punishment_group.name, type=self.punishment_group.type)
        except Exception:
            pass
        try:
            self.bot.tree.remove_command("punish", type=discord.AppCommandType.chat_input)
        except Exception:
            pass

    def _is_admin(self, member: discord.Member) -> bool:
        perms = member.guild_permissions
        return perms.manage_guild or perms.administrator

    def _can_modify(self, invoker: discord.Member, target: discord.Member) -> bool:
        return invoker.id == target.id or self._is_admin(invoker)

    async def _get_punishments(self, member: discord.Member) -> list[dict[str, Any]]:
        return list(await self.config.member(member).punishments())

    async def _get_rules(self, member: discord.Member) -> list[dict[str, Any]]:
        return list(await self.config.member(member).rules())

    async def _add_punishment(self, member: discord.Member, *, text: str, weight: int) -> int:
        conf = self.config.member(member)
        pid = await conf.next_punishment_id()
        await conf.next_punishment_id.set(pid + 1)

        items = list(await conf.punishments())
        items.append({"id": pid, "text": text, "weight": weight})
        await conf.punishments.set(items)
        return pid

    async def _edit_punishment(self, member: discord.Member, *, punishId: int, text: str, weight: int) -> bool:
        conf = self.config.member(member)
        items = list(await conf.punishments())
        for item in items:
            if int(item.get("id", -1)) == punishId:
                item["text"] = text
                item["weight"] = weight
                await conf.punishments.set(items)
                return True
        return False

    async def _remove_punishment(self, member: discord.Member, *, punishId: int) -> bool:
        conf = self.config.member(member)
        items = list(await conf.punishments())
        new_items = [it for it in items if int(it.get("id", -1)) != punishId]
        if len(new_items) == len(items):
            return False
        await conf.punishments.set(new_items)
        return True

    async def _add_rule(self, member: discord.Member, *, text: str) -> int:
        conf = self.config.member(member)
        ruleId = await conf.next_rule_id()
        await conf.next_rule_id.set(ruleId + 1)

        items = list(await conf.rules())
        items.append({"id": ruleId, "text": text})
        await conf.rules.set(items)
        return ruleId

    async def _edit_rule(self, member: discord.Member, *, ruleId: int, text: str) -> bool:
        conf = self.config.member(member)
        items = list(await conf.rules())
        for item in items:
            if int(item.get("id", -1)) == ruleId:
                item["text"] = text
                await conf.rules.set(items)
                return True
        return False

    async def _remove_rule(self, member: discord.Member, *, ruleId: int) -> bool:
        conf = self.config.member(member)
        items = list(await conf.rules())
        new_items = [item for item in items if int(item.get("id", -1)) != ruleId]
        if len(new_items) == len(items):
            return False
        await conf.rules.set(new_items)
        return True
    
    def _chunk_lines(self, lines: list[str], per_page: int) -> list[list[str]]:
        return [lines[i : i + per_page] for i in range(0, len(lines), per_page)]

    def _embeds_from_lines(self, *, title: str, lines: list[str], footer: str) -> list[discord.Embed]:
        if not lines:
            embed = discord.Embed(title=title, description="(none)")
            embed.set_footer(text=footer)
            return [embed]

        pages = self._chunk_lines(lines, MAX_LIST_LINES_PER_PAGE)
        embeds: list[discord.Embed] = []
        for i, page in enumerate(pages, start=1):
            embed = discord.Embed(title=title, description="\n".join(page))
            embed.set_footer(text=f"{footer} - Page {i}/{len(pages)}")
            embeds.append(embed)
        return embeds

    def _build_app_commands(self) -> None:
        @self.punishment_group.command(name="help", description="Show punishment commands.")
        async def punishment_help(interaction: discord.Interaction):
            lines = [
                "**/punishment add** — Add a punishment.",
                "**/punishment edit <id>** — Edit an existing punishment.",
                "**/punishment remove <id>** — Remove a punishment.",
                "**/punishment list [user]** — List punishments.",
                "",
                "**/punishment rules help** — Show rules commands.",
                "**/punishment rules add** — Add a rule.",
                "**/punishment rules edit <id>** — Edit a rule.",
                "**/punishment rules remove <id>** — Remove a rule.",
                "**/punishment rules list [user] [public=false]** — List rules. If you set the public flag, it'll print out for everyone!",
                "",
                "**/punish [user] [obey_weightings=true] [rolls=1] [allow_duplicates=true]** — Roll an amount of punishments, optionally ignoring their set weightings and optionally allowing duplicate rolls.",
            ]
            embeds = self._embeds_from_lines(title="Punishments Help", lines=lines, footer="Punishments")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

        @self.punishment_group.command(name="add", description="Add a punishment to your table.")
        async def punishment_add(interaction: discord.Interaction):
            await interaction.response.send_modal(PunishmentModal(cog=self, target=interaction.user, mode="add"))

        @self.punishment_group.command(name="edit", description="Edit a punishment by ID.")
        @app_commands.describe(id="Punishment ID")
        async def punishment_edit(interaction: discord.Interaction, id: int):
            target = interaction.user
            items = await self._get_punishments(target)
            match = next((item for item in items if int(item.get("id", -1)) == id), None)
            if not match:
                return await interaction.response.send_message(f"Couldn't find punishment **#{id}** on your table.", ephemeral=True)

            await interaction.response.send_modal(
                PunishmentModal(cog=self,target=target,mode="edit",edit_id=id,default_text=str(match.get("text", "")),default_weight=str(match.get("weight", 1)))
            )

        @self.punishment_group.command(name="remove", description="Remove a punishment by ID.")
        @app_commands.describe(id="Punishment ID")
        async def punishment_remove(interaction: discord.Interaction, id: int, user: Optional[discord.Member] = None):
            target = interaction.user
            ok = await self._remove_punishment(target, punishId=id)

            if not ok:
                return await interaction.response.send_message(f"Couldn't find punishment **#{id}** on your table.",ephemeral=True)

            await interaction.response.send_message(f"Removed punishment **#{id}**.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

        @self.punishment_group.command(name="list", description="List punishments for a user.")
        @app_commands.describe(user="User's to view (defaults to you).")
        async def punishment_list(interaction: discord.Interaction, user: Optional[discord.Member] = None):
            target = user or interaction.user
            if not isinstance(target, discord.Member):
                return await interaction.response.send_message("That user isn't in this server.", ephemeral=True)

            items = await self._get_punishments(target)
            if not items:
                return await interaction.response.send_message(f"{target.mention} has no punishments yet.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

            lines = [f"**#{item['id']}** — {discord.utils.escape_markdown(str(item.get('text','')))} (w:{item.get('weight',1)})" for item in items]
            embeds = self._embeds_from_lines(title=f"Punishments for {target}", lines=lines, footer="ChatRules")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

        @self.rules_group.command(name="help", description="Show rules commands.")
        async def rules_help(interaction: discord.Interaction):
            lines = ["**/punishment rules add** — Add a rule (modal).",
                "**/punishment rules edit <id>** — Edit a rule.",
                "**/punishment rules remove <id>** — Remove a rule.",
                "**/punishment rules list [user] [public=false]** — List rules."]
            embeds = self._embeds_from_lines(title="Rules Help", lines=lines, footer="ChatRules")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)

        @self.rules_group.command(name="add", description="Add a rule to your list.")
        async def rules_add(interaction: discord.Interaction):
            await interaction.response.send_modal(RuleModal(cog=self, target=interaction.user, mode="add"))

        @self.rules_group.command(name="edit", description="Edit a rule by ID.")
        @app_commands.describe(id="Rule ID")
        async def rules_edit(interaction: discord.Interaction, id: int, user: Optional[discord.Member] = None):
            target = interaction.user
            if not self._can_modify(interaction.user, target):
                return await interaction.response.send_message("You can only modify your own rules (unless you're an admin).", ephemeral=True)

            items = await self._get_rules(target)
            match = next((it for it in items if int(it.get("id", -1)) == id), None)
            if not match:
                return await interaction.response.send_message(f"Couldn't find rule **#{id}** in your list.", ephemeral=True)

            await interaction.response.send_modal(
                RuleModal(cog=self, target=target, mode="edit", edit_id=id, default_text=str(match.get("text", "")))
            )

        @self.rules_group.command(name="remove", description="Remove a rule by ID.")
        @app_commands.describe(id="Rule ID")
        async def rules_remove(interaction: discord.Interaction, id: int, user: Optional[discord.Member] = None):
            target = interaction.user

            ok = await self._remove_rule(target, ruleId=id)

            if not ok:
                return await interaction.response.send_message(f"Couldn't find rule **#{id}** in your list.", ephemeral=True)

            await interaction.response.send_message(f"Removed rule **#{id}**.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

        @self.rules_group.command(name="list", description="List rules for a user.")
        @app_commands.describe(user="User to view (defaults to you).", public="If true, posts publicly instead of just for you.")
        async def rules_list(interaction: discord.Interaction, user: Optional[discord.Member] = None, public: bool = False):

            target = user or interaction.user
            if not isinstance(target, discord.Member):
                return await interaction.response.send_message("That user isn't in this server.", ephemeral=True)

            items = await self._get_rules(target)
            if not items:
                return await interaction.response.send_message(f"{target.mention} has no rules yet.", ephemeral=not public, allowed_mentions=discord.AllowedMentions.none())

            lines = [f"**#{it['id']}** — {discord.utils.escape_markdown(str(it.get('text','')))}" for it in items]
            embeds = self._embeds_from_lines(title=f"Rules for {target}", lines=lines, footer="ChatRules")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=not public)

        @app_commands.command(name="punish", description="Roll punishments for a user.")
        @app_commands.describe(user="User to punish (defaults to you).",
            obey_weightings="If true, uses weights; if false, treats all weights as 1.",
            rolls=f"How many rolls to make (1-{MAX_ROLLS}).",
            allow_duplicates="If false, each roll is unique (no duplicates).")
        async def punish_root(interaction: discord.Interaction, user: Optional[discord.Member] = None, obey_weightings: bool = True, rolls: app_commands.Range[int, 1, MAX_ROLLS] = 1, allow_duplicates: bool = True):
            target = user or interaction.user
            if not isinstance(target, discord.Member):
                return await interaction.response.send_message("That user isn't in this server.", ephemeral=True)

            items = await self._get_punishments(target)
            if not items:
                return await interaction.response.send_message(f"{target.mention} has no punishments yet. Use `/punishment add`.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

            if not allow_duplicates and rolls > len(items):
                return await interaction.response.send_message(f"Not enough punishments to roll {rolls} unique results (they have {len(items)}).", ephemeral=True)

            def weight_of(it: dict[str, Any]) -> int:
                if not obey_weightings:
                    return 1
                try:
                    weight = int(it.get("weight", 1))
                except Exception:
                    weight = 1
                return max(1, min(WEIGHT_MAX, weight))

            chosen: list[dict[str, Any]] = []
            if allow_duplicates:
                weights = [weight_of(item) for item in items]
                chosen = random.choices(items, weights=weights, k=rolls)
            else:
                pool = items[:]
                for _ in range(rolls):
                    weights = [weight_of(it) for it in pool]
                    pick = random.choices(pool, weights=weights, k=1)[0]
                    chosen.append(pick)
                    pick_id = int(pick.get("id", -1))
                    pool = [item for item in pool if int(item.get("id", -1)) != pick_id]

            lines = [f"- **#{item.get('id','?')}** — {discord.utils.escape_markdown(str(item.get('text','')))}" for item in chosen]

            embed = discord.Embed(title="Punishment Roll", description=f"{target.mention}\n\n" + "\n".join(lines))
            embed.set_footer(text=f"obey_weightings={obey_weightings} - allow_duplicates={allow_duplicates} - rolls={rolls}")

            await interaction.response.send_message(embed=embed, ephemeral=False, allowed_mentions=discord.AllowedMentions(users=[target]))

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="add", description="Add a punishment to another user's table.")
        @app_commands.describe(user="Target user")
        async def admin_punishment_add(interaction: discord.Interaction, user: discord.Member):
            await interaction.response.send_modal(PunishmentModal(cog=self, target=user, mode="add"))

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="edit", description="Edit a punishment in another user's table.")
        @app_commands.describe(user="Target user", id="Punishment ID")
        async def admin_punishment_edit(interaction: discord.Interaction, user: discord.Member, id: int):
            items = await self._get_punishments(user)
            match = next((it for it in items if int(it.get("id", -1)) == id), None)
            if not match:
                return await interaction.response.send_message(f"Couldn't find punishment **#{id}** for {user.mention}.", ephemeral=True)

            await interaction.response.send_modal(
                PunishmentModal(cog=self, target=user, mode="edit", edit_id=id, default_text=str(match.get("text", "")), default_weight=str(match.get("weight", 1)))
            )

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="remove", description="Remove a punishment from another user's table.")
        @app_commands.describe(user="Target user", id="Punishment ID")
        async def admin_punishment_remove(interaction: discord.Interaction, user: discord.Member, id: int):
            ok = await self._remove_punishment(user, pid=id)
            if not ok:
                return await interaction.response.send_message(f"Couldn’t find punishment **#{id}** for {user.mention}.", ephemeral=True)

            await interaction.response.send_message(f"Removed punishment **#{id}** for {user.mention}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="rules_add", description="Add a rule to another user's list.")
        @app_commands.describe(user="Target user")
        async def admin_rules_add(interaction: discord.Interaction, user: discord.Member):
            assert interaction.guild is not None
            await interaction.response.send_modal(RuleModal(cog=self, target=user, mode="add"))

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="rules_edit", description="Edit a rule in another user's list.")
        @app_commands.describe(user="Target user", id="Rule ID")
        async def admin_rules_edit(interaction: discord.Interaction, user: discord.Member, id: int):
            items = await self._get_rules(user)
            match = next((item for item in items if int(item.get("id", -1)) == id), None)
            if not match:
                return await interaction.response.send_message(f"Couldn't find rule **#{id}** for {user.mention}.", ephemeral=True)

            await interaction.response.send_modal(
                RuleModal(cog=self, target=user, mode="edit", edit_id=id, default_text=str(match.get("text", "")))
            )

        @app_commands.default_permissions(manage_guild=True)
        @app_commands.checks.has_permissions(manage_guild=True)
        @self.admin_group.command(name="rules_remove", description="Remove a rule from another user's list.")
        @app_commands.describe(user="Target user", id="Rule ID")
        async def admin_rules_remove(interaction: discord.Interaction, user: discord.Member, id: int):
            ok = await self._remove_rule(user, rid=id)
            if not ok:
                return await interaction.response.send_message(f"Couldn't find rule **#{id}** for {user.mention}.", ephemeral=True)

            await interaction.response.send_message(f"Removed rule **#{id}** for {user.mention}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

        self.bot.tree.add_command(punish_root)