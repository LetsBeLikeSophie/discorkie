from discord.ext import commands
from discord import app_commands, Interaction
import aiohttp

class Affixes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="어픽스", description="이번 주 어픽스를 보여드려요!")
    async def show_affixes(self, interaction: Interaction):
        await interaction.response.defer()

        url = "https://raider.io/api/v1/mythic-plus/affixes?region=kr&locale=ko"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("어픽스 정보를 불러오지 못했어요 😢")
                    return

                data = await resp.json()
                title = data.get("title", "이번 주 어픽스")
                affixes = data.get("affix_details", [])

                # 숫자 이모티콘
                emojis = [":one:", ":two:", ":three:", ":four:"]
                msg = f"**{title}**\n\n"

                for i, affix in enumerate(affixes[:4]):
                    name = affix.get("name", "이름 없음")
                    desc = affix.get("description", "설명 없음")
                    msg += f"{emojis[i]} **{name}**: {desc}\n"

                await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(Affixes(bot))
