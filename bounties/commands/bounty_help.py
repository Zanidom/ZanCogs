import discord

def register(bounty_group, cog):
    @bounty_group.command(name="help", description="How bounties work.")
    async def help_cmd(interaction: discord.Interaction):
        text = (
            "**Bounty flow (normal mode)**\n"
            "1) Buyer posts a bounty: `/bounty add`\n"
            "2) People apply: `/bounty apply <id|title>`\n"
            "3) Buyer accepts: `/bounty accept <id|title> @user` (reward is escrowed)\n"
            "4) Accepted user fulfils: `/bounty fulfil <id|title>`\n"
            "5) Buyer pays out: `/bounty payout <id|title> @user`\n\n"
            "**Open fulfil mode**\n"
            "- Anyone can submit fulfilment: `/bounty fulfil <id|title>`\n"
            "- Buyer pays out directly at payout time: `/bounty payout <id|title> @user`\n\n"
            "**Useful commands**\n"
            "- Browse: `/bounty board`, `/bounty list`, `/bounty view <id|title>`\n"
            "- Your bounties: `/bounty mine`\n"
            "- Edit/remove: `/bounty edit <id|title>`, `/bounty remove <id|title>`\n"
        )
        await interaction.response.send_message(text, ephemeral=True)
