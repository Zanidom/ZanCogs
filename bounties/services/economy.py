from __future__ import annotations

from redbot.core import bank
import discord


class EconomyService:
    async def can_spend(self, member: discord.Member, amount: int) -> bool:
        return await bank.can_spend(member, amount)

    async def withdraw(self, member: discord.Member, amount: int) -> None:
        await bank.withdraw_credits(member, amount)

    async def deposit(self, member: discord.Member, amount: int) -> None:
        await bank.deposit_credits(member, amount)
