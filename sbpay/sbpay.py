import math
import discord
from redbot.core import commands, checks, bank, errors
from redbot.core.utils.chat_formatting import humanize_number


class SBPay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @checks.admin_or_permissions(manage_guild=True)
    @commands.command(name="sbpay")
    async def _pay(self, ctx: commands.Context, to: discord.Member, amount: int):
        """Pay a member from the Slutbot reserves."""
        from_ = ctx.message.guild.get_member(self.bot.user.id)
        print(from_)
        currency = await bank.get_currency_name(ctx.guild)

        try:
            await bank.transfer_credits(from_, to, amount)
        except (ValueError, errors.BalanceTooHigh) as e:
            return await ctx.send(str(e))

        await ctx.send(
            ("{user} transferred {num} {currency} to {other_user}").format(
                user=from_.display_name,
                num=humanize_number(amount),
                currency=currency,
                other_user=to.display_name,
            )
        )
