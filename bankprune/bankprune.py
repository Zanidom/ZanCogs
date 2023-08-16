from enum import member
from discord import Member
from redbot.core import commands, checks, bank
from redbot.core.utils import AsyncIter

class Bankpruner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bankprune")
    @checks.admin_or_permissions(manage_guild=True)
    async def _bank_prune(self, ctx, target_member: Member = None):
        """Prune bank accounts of members no longer in the server and transfer their balance to the mentioned user."""
        if target_member is None:
            await ctx.send("Please use ;bankprune @target to transfer pruned accounts to the target account.")
            return

        _guild = ctx.guild
        group = bank._config._get_base_group(bank._config.MEMBER, str(_guild.id))
        
        await _guild.chunk()
        accounts = await group.all()
        tmp = accounts.copy()
        members = ctx.guild.members
        user_list = {str(m.id) for m in members}

        totTrans = 0
        outputStr = "Transaction list:\n```"
        async with group.all() as bank_data:  # FIXME: use-config-bulk-update
            for acc in tmp:
                if acc not in user_list:
                    val = bank_data[acc]["balance"]
                    outputStr += f"Deleting {acc} with {val}\n"
                    totTrans += bank_data[acc]["balance"]
                    del bank_data[acc]
        
        outputStr += "```"
        await bank.deposit_credits(target_member, totTrans);

        if totTrans != 0:
            await ctx.send(outputStr)

        await ctx.send(f"{totTrans} purged from accounts and added to {target_member}'s account.")