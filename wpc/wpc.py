from redbot.core import Config, commands, checks
import discord

UNIQUE_ID = 0x10101010101010  # replace this with a unique ID

class WPC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=UNIQUE_ID, force_registration=True)

        default_guild = {
            "target_role": None,
            "authorized_users": []
        }

        self.config.register_guild(**default_guild)

    @commands.guild_only()
    @commands.group()
    async def wpc(self, ctx):
        """WPC commands"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()

    @wpc.command(name="set")
    @checks.admin_or_permissions(manage_roles=True)
    async def wpc_set(self, ctx, *, role: discord.Role):
        """Set the target role."""
        await self.config.guild(ctx.guild).target_role.set(role.id)
        await ctx.send(f"Target role set to {role.name}.")

    @wpc.command(name="winner")
    async def wpc_winner(self, ctx, *, member: discord.Member):
        """Assign the target role to the specified member and remove from others."""
        authorized_users = await self.config.guild(ctx.guild).authorized_users()
        if ctx.author.id not in authorized_users and not ctx.author.guild_permissions.administrator:
            await ctx.send("You are not authorized to use this command.")
            return
        
        target_role_id = await self.config.guild(ctx.guild).target_role()
        if not target_role_id:
            await ctx.send("Target role has not been set!")
            return
        
        target_role = ctx.guild.get_role(target_role_id)
        if not target_role:
            await ctx.send("The set target role no longer exists!")
            return

        for m in target_role.members:
            await m.remove_roles(target_role)

        await member.add_roles(target_role)
        await ctx.send(f"{member.mention} is now the WPC winner!")

    @wpc.command(name="adduser")
    @checks.admin_or_permissions(manage_roles=True)
    async def wpc_adduser(self, ctx, *, member: discord.Member):
        """Authorize a user to use the winner command."""
        async with self.config.guild(ctx.guild).authorized_users() as authorized:
            if member.id not in authorized:
                authorized.append(member.id)
                await ctx.send(f"{member.mention} has been authorized to use the winner command.")
            else:
                await ctx.send(f"{member.mention} is already authorized.")

    @wpc.command(name="removeuser")
    @checks.admin_or_permissions(manage_roles=True)
    async def wpc_removeuser(self, ctx, *, member: discord.Member):
        """Deauthorize a user from using the winner command."""
        async with self.config.guild(ctx.guild).authorized_users() as authorized:
            if member.id in authorized:
                authorized.remove(member.id)
                await ctx.send(f"{member.mention} has been deauthorized from using the winner command.")
            else:
                await ctx.send(f"{member.mention} was not previously authorized.")