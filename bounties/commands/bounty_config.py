from __future__ import annotations
from typing import Union
import discord
from redbot.core import app_commands

Messageable = Union[discord.TextChannel, discord.Thread]

def register(config_group: app_commands.Group, cog):
    def admin_only(member: discord.Member) -> bool:
        p = member.guild_permissions
        return p.administrator or p.manage_guild or p.manage_messages

    @config_group.command(name="audit_channel", description="Set the audit log channel or thread for bounty events.")
    @app_commands.guild_only()
    async def audit_channel(interaction: discord.Interaction, channel: Messageable):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if not admin_only(interaction.user):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        await cog.config.guild(interaction.guild).audit_channel_id.set(channel.id)
        await interaction.response.send_message(f"Audit channel set to {channel.mention}.", ephemeral=True)

    @config_group.command(name="board_channel", description="Set the bounty board channel or thread.")
    @app_commands.guild_only()
    async def board_channel(interaction: discord.Interaction, channel: Messageable):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if not admin_only(interaction.user):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        await cog.config.guild(interaction.guild).board_channel_id.set(channel.id)
        await interaction.response.send_message(f"Board channel set to {channel.mention}.", ephemeral=True)

    @config_group.command(name="add_cost", description="Set the cost to post a bounty.")
    @app_commands.guild_only()
    async def add_cost(interaction: discord.Interaction, amount: int):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if not admin_only(interaction.user):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return
        if amount < 0:
            await interaction.response.send_message("Amount must be >= 0.", ephemeral=True)
            return

        await cog.config.guild(interaction.guild).add_cost.set(amount)
        await interaction.response.send_message(f"Cost to add a bounty set to {amount}.", ephemeral=True)

    @config_group.command(name="block", description="Block a user from all bounty commands.")
    @app_commands.guild_only()
    async def block(interaction: discord.Interaction, user: discord.Member):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if not admin_only(interaction.user):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        async with cog.config.guild(interaction.guild).blocked_user_ids() as bl:
            if user.id not in bl:
                bl.append(user.id)

        await interaction.response.send_message(f"Blocked {user.mention} from bounty commands.", ephemeral=True)

    @config_group.command(name="unblock", description="Unblock a user from bounty commands.")
    @app_commands.guild_only()
    async def unblock(interaction: discord.Interaction, user: discord.Member):
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        if not admin_only(interaction.user):
            await interaction.response.send_message("Admins only.", ephemeral=True)
            return

        async with cog.config.guild(interaction.guild).blocked_user_ids() as bl:
            if user.id in bl:
                bl.remove(user.id)

        await interaction.response.send_message(f"Unblocked {user.mention}.", ephemeral=True)
