from redbot.core import commands, bank
import discord
import re

class Tax(commands.Cog):
    """Tax users by amount or percentage."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)  
    async def tax(self, ctx, member: discord.Member, amount: str):
        """
        Tax a user.
        Usage: [p]tax @user <amount or %>
        Example: [p]tax @user 100
                 [p]tax @user 10%
        """
        currency = await bank.get_currency_name(ctx.guild)

        match = re.match(r"^(\d+)%$", amount)
        if match:
            try:
                percent = int(match.group(1))
                if percent < 0 or percent > 100:
                    return await ctx.send("Percentage must be between 0 and 100.")
                balance = await bank.get_balance(member)
                tax_amount = int(balance * (percent / 100))
            except ValueError:
                return await ctx.send("Please provide a valid amount or percentage.")
        else:
            try:
                tax_amount = int(amount)
            except ValueError:
                return await ctx.send("Please provide a valid amount or percentage.")

        if tax_amount <= 0:
            return await ctx.send("Tax amount must be greater than 0.")

        balance = await bank.get_balance(member)
        if tax_amount > balance:
            return await ctx.send(f"{member.display_name} doesn’t have enough {currency}.")

        await bank.withdraw_credits(member, tax_amount)

        await ctx.send(
            f"{ctx.author.display_name} removed "
            f"{tax_amount:,} {currency} from **{member.display_name}**'s account."
        )

async def setup(bot):
    await bot.add_cog(Tax(bot))
