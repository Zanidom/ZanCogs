from __future__ import annotations

import random
from typing import Any, Optional

import discord
from discord import app_commands

from redbot.core import commands, Config
from redbot.core.bot import Red

import io
import csv
import re


from .constants import CONFIG_IDENTIFIER, MAX_LIST_LINES_PER_PAGE, MAX_ROLLS, WEIGHT_MAX, PAGINATOR_TIMEOUT, CLONE_CONFIRM_TIMEOUT, ID_SPLIT_RE
from .ui.importer import ImportPunishmentsModal
from .ui.paginator import EmbedPaginator
from .ui.confirm import ConfirmView
from .ui.modals import PunishmentModal, RuleModal


#static func just because
def _parse_ids(ids: str) -> list[int]: 
    out: list[int] = []
    for token in ID_SPLIT_RE.split(ids.strip()):
        if not token:
            continue
        try:
            out.append(int(token))
        except ValueError:
            continue
    #preserve order, drop duplicates
    seen = set()
    deduped = []
    for i in out:
        if i not in seen:
            seen.add(i)
            deduped.append(i)
    return deduped

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

    async def _get_enabled_punishments(self, member: discord.Member) -> list[dict]:
        items = await self._get_punishments(member)
        return [it for it in items if it.get("enabled", True)]

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

    async def _bulk_add_punishments(self, member: discord.Member, *, texts: list[str], weight: int) -> int:
        conf = self.config.member(member)

        next_id = await conf.next_punishment_id()
        items = list(await conf.punishments())
        count = 0

        for text in texts:
            punishId = next_id
            next_id += 1
            count += 1

            items.append(
                {
                    "id": punishId,
                    "text": text,
                    "weight": weight,
                }
            )

        await conf.punishments.set(items)
        await conf.next_punishment_id.set(next_id)
        return count

    async def _set_punishments_enabled(self, member: discord.abc.User, guild_id: int, ids: list[int], enabled: bool):
        conf = self.config.member_from_ids(guild_id, member.id)
        items = list(await conf.punishments())

        found = set()
        for item in items:
            punishId = int(item.get("id", -1))
            if punishId in ids:
                item["enabled"] = enabled
                found.add(punishId)

        if found:
            await conf.punishments.set(items)

        missing = [id for id in ids if id not in found]
        return sorted(found), missing

    async def _bulk_add_punishments_with_weights(self, member: discord.Member, *, items: list[tuple[str, int]] ) -> list[int]:
        conf = self.config.member(member)

        next_id = await conf.next_punishment_id()
        current = list(await conf.punishments())

        ids: list[int] = []

        for desc, weight in items:
            pid = next_id
            next_id += 1
            ids.append(pid)

            current.append({"id": pid, "text": desc, "weight": weight})

        await conf.punishments.set(current)
        await conf.next_punishment_id.set(next_id)

        return ids


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

    def _format_punishment_line(self, item: dict) -> str:
        text = discord.utils.escape_markdown(str(item.get("text", "")))
        weight = item.get("weight", 1)
        suffix = "" if item.get("enabled", True) else " *(disabled)*"
        return f"**#{item['id']}** - {text} (w:{weight}){suffix}"


    def _build_app_commands(self) -> None:
        @self.punishment_group.command(name="help", description="Show punishment commands.")
        async def punishment_help(interaction: discord.Interaction):
            lines = [
                "**/punishment add** - Add a punishment.",
                "**/punishment edit <id>** - Edit an existing punishment.",
                "**/punishment remove <id>** - Remove a punishment.",
                "**/punishment list [user]** - List punishments.",
                "**/punishment enable <ids>** - Enable punishments for given IDs (comma-separated list)",
                "**/punishment disable <ids>** - Disable punishments for given IDs (comma-separated list)",

                "",
                "**/punishment rules help** - Show rules commands.",
                "**/punishment rules add** - Add a rule.",
                "**/punishment rules edit <id>** - Edit a rule.",
                "**/punishment rules remove <id>** - Remove a rule.",
                "**/punishment rules list [user] [public=false]** - List rules. If you set the public flag, it'll print out for everyone!",
                "",
                "**/punishment clone <from_server_id>** - Clone your punishments/rules from another server into this one (OVERWRITES).",
                "**/punishment import** - Bulk-import punishments from a pasted text list.",
                "**/punishment forgetme [export]** - Permanently erase your stored punishments/rules in this server. Optionally get an export for yourself.",
                "",
                "**/punish [user] [obey_weightings=true] [rolls=1] [allow_duplicates=true]** - Roll an amount of punishments, optionally ignoring their set weightings and optionally allowing duplicate rolls.",
            ]
            embeds = self._embeds_from_lines(title="Punishments Help", lines=lines, footer="Punishments")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)
            view.message = await interaction.original_response()


        @self.punishment_group.command(name="clone", description="Clone your punishments/rules from another server into this one (OVERWRITES!!!).")
        @app_commands.describe(from_server_id="Server ID to copy FROM (source). Run this command in the server you want to copy INTO.")
        async def punishment_clone(interaction: discord.Interaction, from_server_id: str):
            try:
                source_guild_id = int(from_server_id.strip())
            except ValueError:
                return await interaction.response.send_message("That doesn't look like a valid server ID (it must be a number - @ Zan if you need help with this).", ephemeral=True)

            target_guild_id = interaction.guild.id
            if source_guild_id == target_guild_id:
                return await interaction.response.send_message("You're already in that server. Nothing to clone, silly.", ephemeral=True)

            source_guild = self.bot.get_guild(source_guild_id)
            source_name = source_guild.name if source_guild else "Unknown (bot may not be in that server?)"
            target_name = interaction.guild.name

            source_conf = self.config.member_from_ids(source_guild_id, interaction.user.id)
            target_conf = self.config.member(interaction.user)

            source_puns = list(await source_conf.punishments())
            source_rules = list(await source_conf.rules())

            target_puns = list(await target_conf.punishments())
            target_rules = list(await target_conf.rules())

            if not source_puns and not source_rules:
                return await interaction.response.send_message(f"No punishments or rules for you in the source server (**{source_name}**, `{source_guild_id}`)...?", ephemeral=True)

            warn_lines = [
                "WARNING: This will OVERWRITE your current lists in this server",
                "",
                f"**Source server:** {source_name} (`{source_guild_id}`)",
                f"- Punishments: **{len(source_puns)}**",
                f"- Rules: **{len(source_rules)}**",
                "",
                f"**Target server (this one):** {target_name} (`{target_guild_id}`)",
                f"- Punishments currently here: **{len(target_puns)}**",
                f"- Rules currently here: **{len(target_rules)}**",
                "",
                "If you click **CONFIRM CLONE**, your target lists will be replaced with the source lists.",
                "This cannot be undone.",
            ]

            embed = discord.Embed(title="Clone punishments/rules from another server", description="\n".join(warn_lines))

            view = ConfirmView(author_id=interaction.user.id, timeout=CLONE_CONFIRM_TIMEOUT)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            await view.wait()

            if view.confirmed is None:
                return

            if view.confirmed is False:
                return await interaction.followup.send("Clone cancelled.", ephemeral=True)

            await target_conf.punishments.set(source_puns)
            await target_conf.rules.set(source_rules)

            source_next_pun = await source_conf.next_punishment_id()
            source_next_rule = await source_conf.next_rule_id()

            await target_conf.next_punishment_id.set(source_next_pun)
            await target_conf.next_rule_id.set(source_next_rule)

            await interaction.followup.send(f"Successfully cloned from **{source_name}** into **{target_name}**.\n"
                f"- Punishments now: **{len(source_puns)}**\n"
                f"- Rules now: **{len(source_rules)}**", ephemeral=True)

        @self.punishment_group.command(name="add", description="Add a punishment to your table.")
        async def punishment_add(interaction: discord.Interaction):
            await interaction.response.send_modal(PunishmentModal(cog=self, target=interaction.user, mode="add"))


        @self.punishment_group.command(name="import", description="Bulk-import punishments from the old bot's text list output.")
        async def punishment_import(interaction: discord.Interaction):
            assert interaction.guild is not None
            assert isinstance(interaction.user, discord.Member)

            await interaction.response.send_modal(
                ImportPunishmentsModal(cog=self, target=interaction.user)
            )


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
        @app_commands.describe(user="Which user to view (defaults to you).", public="If true, posts publicly instead of ephemerally.", show_disabled="If True, additionally shows disabled punishments.")
        async def punishment_list(interaction: discord.Interaction, user: Optional[discord.Member] = None, public: bool = False, show_disabled: bool = False):
            target = user or interaction.user
            if not isinstance(target, discord.Member):
                return await interaction.response.send_message("Couldn't find that user in this server.", ephemeral=True)

            items = await self._get_punishments(target)
            if not show_disabled:
                items = [item for item in items if item.get("enabled", True)]

            if not items:
                msg = (f"{target.mention} has no punishments yet." if show_disabled else f"{target.mention} has no enabled punishments.")
                return await interaction.response.send_message(msg, ephemeral=(not public), allowed_mentions=discord.AllowedMentions.none())

            lines = [self._format_punishment_line(item) for item in items]
            embeds = self._embeds_from_lines(title=f"Punishments for {target}", lines=lines, footer="Punishment List")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT, self_restriction=False)

            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=not public, allowed_mentions=discord.AllowedMentions.none())
            view.message = await interaction.original_response()



        @self.punishment_group.command(name="forgetme", description="Erase all your stored punishments/rules in this server.")
        @app_commands.describe(export="Do you want an export of your data? Set this to True if so.")
        async def punishment_forgetme(interaction: discord.Interaction, export: bool = False):
            conf = self.config.member(interaction.user)

            punishments = list(await conf.punishments())
            rules = list(await conf.rules())
            if not punishments and not rules:
                return await interaction.response.send_message("You don't have any stored punishments or rules in this server.", ephemeral=True)

            lines = ["FORGET ME (DATA DELETION)",
                "",
                "This will permanently erase **your** stored data in **this server only**:",
                f"- Punishments: **{len(punishments)}**",
                f"- Rules: **{len(rules)}**",
                "",
                "This cannot be undone. If you want your data restored you will have to reimport it.",
                "Click **Confirm** to proceed.",
            ]

            embed = discord.Embed(title="Confirm deletion", description="\n".join(lines))

            view = ConfirmView(author_id=interaction.user.id, confirm_label="Confirm", confirm_style=discord.ButtonStyle.danger, cancel_label="Cancel", timeout=120)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            await view.wait()

            if view.confirmed is None:
                return

            if view.confirmed is False:
                return await interaction.followup.send("Deletion cancelled.", ephemeral=True)

            if export:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["id", "desc", "weight"])
    
                for item in punishments:
                    writer.writerow([
                        int(item.get("id", 0)),
                        str(item.get("text", "")),
                        int(item.get("weight", 1)),
                    ])
    
                data = output.getvalue().encode("utf-8")
                output.close()
    
                filename = f"punishments_{interaction.guild.id}_{interaction.user.id}.csv"
                file = discord.File(fp=io.BytesIO(data), filename=filename)

                try:
                    await interaction.user.send(content="Here's your punishment export CSV (keep it safe if you want to re-import later).", file=file)
                except discord.Forbidden:
                    return await interaction.followup.send(
                        "I couldn't DM you the export of your data (your DMs are closed or you blocked the bot)."
                        "I **won't** delete anything yet.\n\n"
                        "Please enable DMs temporarily and run `/punishment forgetme` again.", ephemeral=True)
                except discord.HTTPException:
                    return await interaction.followup.send(
                        "Something went wrong trying to DM you the export. I **won't** delete anything yet.\n\n"
                        "Please try again in a moment. If this persists, @ Zan", ephemeral=True)

            await conf.punishments.set([])
            await conf.rules.set([])
            await conf.next_punishment_id.set(1)
            await conf.next_rule_id.set(1)
            forgetMeText = "I've DM'd you a CSV backup and erased your stored punishments/rules for this server." if export else "I've deleted all of your data."
            await interaction.followup.send(forgetMeText, ephemeral=True)

        @self.punishment_group.command(name="disable", description="Disable one or more punishments so they can't be rolled.")
        @app_commands.describe(ids="Punishment IDs (e.g. '1,2,3' or '1 2 3').")
        async def punishment_disable(interaction: discord.Interaction, ids: str):
            assert interaction.guild is not None
            target = interaction.user 
            parsed = _parse_ids(ids)
            if not parsed:
                return await interaction.response.send_message("No valid IDs found.", ephemeral=True)

            found, missing = await self._set_punishments_enabled(target, interaction.guild.id, parsed, enabled=False)

            msg = f"Disabled: {', '.join(f'#{i}' for i in found) if found else '(none)'}"
            if missing:
                msg += f"\nNot found: {', '.join(f'#{i}' for i in missing)}"
            await interaction.response.send_message(msg, ephemeral=True)


        @self.punishment_group.command(name="enable", description="Enable one or more punishments so they can be rolled again.")
        @app_commands.describe(ids="Punishment IDs (e.g. '1,2,3' or '1 2 3').")
        async def punishment_enable(interaction: discord.Interaction, ids: str):
            target = interaction.user 
            parsed = _parse_ids(ids)
            if not parsed:
                return await interaction.response.send_message("No valid IDs found.", ephemeral=True)

            found, missing = await self._set_punishments_enabled(target, interaction.guild.id, parsed, enabled=True)

            msg = f"Enabled: {', '.join(f'#{i}' for i in found) if found else '(none)'}"
            if missing:
                msg += f"\nNot found: {', '.join(f'#{i}' for i in missing)}"
            await interaction.response.send_message(msg, ephemeral=True)


        @self.rules_group.command(name="help", description="Show rules commands.")
        async def rules_help(interaction: discord.Interaction):
            lines = ["**/punishment rules add** - Add a rule (modal).",
                "**/punishment rules edit <id>** - Edit a rule.",
                "**/punishment rules remove <id>** - Remove a rule.",
                "**/punishment rules list [user] [public=false]** - List rules."]
            embeds = self._embeds_from_lines(title="Rules Help", lines=lines, footer="ChatRules")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=True)
            view.message = await interaction.original_response()


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

            lines = [f"**#{it['id']}** - {discord.utils.escape_markdown(str(it.get('text','')))}" for it in items]
            embeds = self._embeds_from_lines(title=f"Rules for {target}", lines=lines, footer="ChatRules")
            view = EmbedPaginator(embeds, author_id=interaction.user.id, timeout=PAGINATOR_TIMEOUT, self_restriction=False)
            await interaction.response.send_message(embed=embeds[0], view=view, ephemeral=not public)
            view.message = await interaction.original_response()


        @app_commands.command(name="punish", description="Roll punishments for a user.")
        @app_commands.describe(user="User to punish (defaults to you).",
            obey_weightings="If true, uses weights; if false, treats all weights as 1.",
            rolls=f"How many rolls to make (1-{MAX_ROLLS}).",
            allow_duplicates="If false, each roll is unique (no duplicates).")
        async def punish_root(interaction: discord.Interaction, user: Optional[discord.Member] = None, obey_weightings: bool = True, rolls: app_commands.Range[int, 1, MAX_ROLLS] = 1, allow_duplicates: bool = True):
            target = user or interaction.user
            if not isinstance(target, discord.Member):
                return await interaction.response.send_message("That user isn't in this server.", ephemeral=True)

            items = await self._get_enabled_punishments(target)
            if not items:
                return await interaction.response.send_message(f"{target.mention} has no enabled punishments. Use `/punishment add`.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

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

            lines = [f"- **#{item.get('id','?')}** - {discord.utils.escape_markdown(str(item.get('text','')))}" for item in chosen]

            embed = discord.Embed(title="Punishment Roll", description=f"{target.mention}\n\n" + "\n".join(lines))
            embed.set_footer(text=f"obey_weightings={obey_weightings} - allow_duplicates={allow_duplicates} - rolls={rolls}")

            await interaction.response.send_message(embed=embed, ephemeral=False, allowed_mentions=discord.AllowedMentions.all())

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
                return await interaction.response.send_message(f"Couldn't find punishment **#{id}** for {user.mention}.", ephemeral=True)

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