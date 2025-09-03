from discord.ext import commands
from discord import app_commands, Interaction
import aiohttp

class RaidProgression(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="길드레이드", description="우리 길드의 레이드 진행도 또는 랭킹을 보여줘요!")
    @app_commands.describe(정보종류="진행도 또는 랭킹을 선택해주세요")
    @app_commands.choices(정보종류=[
        app_commands.Choice(name="진행도", value="raid_progression"),
        app_commands.Choice(name="랭킹", value="raid_rankings")
    ])
    async def guild_raid_info(self, interaction: Interaction, 정보종류: app_commands.Choice[str]):
        await interaction.response.defer()

        field = 정보종류.value
        guild_name_encoded = "우당탕탕 스톰윈드 지구대".replace(" ", "%20")
        url = (
            f"https://raider.io/api/v1/guilds/profile"
            f"?region=kr&realm=hyjal&name={guild_name_encoded}&fields={field}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"❌ 정보를 불러오지 못했어요 (상태 코드: {resp.status})")
                    return

                data = await resp.json()

                if field == "raid_progression":
                    raid = data.get("raid_progression", {}).get("manaforge-omega")
                    if not raid:
                        await interaction.followup.send("진행도 정보를 찾을 수 없어요 😢")
                        return

                    summary = raid.get("summary", "알 수 없음")
                    normal = raid.get("normal_bosses_killed", 0)
                    heroic = raid.get("heroic_bosses_killed", 0)
                    mythic = raid.get("mythic_bosses_killed", 0)

                    msg = (
                        f"💥 **마나 괴철로 종극점 레이드 진행도**\n"
                        f"📌 요약: {summary}\n"
                        f"> 일반 처치: {normal}넴\n"
                        f"> 영웅 처치: {heroic}넴\n"
                        f"> 신화 처치: {mythic}넴"
                    )
                    await interaction.followup.send(msg)

                elif field == "raid_rankings":
                    raid = data.get("raid_rankings", {}).get("manaforge-omega")
                    if not raid:
                        await interaction.followup.send("랭킹 정보를 찾을 수 없어요 😢")
                        return

                    def format_rank(rank):
                        return "없음" if rank == 0 else f"{rank:,}위"

                    msg = (
                        f"🏆 **마나 괴철로 종극점 레이드 랭킹**\n"
                        f"✅ **영웅 난이도**\n"
                        f"- 세계: {format_rank(raid['heroic']['world'])}\n"
                        f"- 아시아: {format_rank(raid['heroic']['region'])}\n"
                        f"- 하이잘: {format_rank(raid['heroic']['realm'])}\n\n"
                        f"💀 **신화 난이도**\n"
                        f"- 세계: {format_rank(raid['mythic']['world'])}\n"
                        f"- 아시아: {format_rank(raid['mythic']['region'])}\n"
                        f"- 하이잘: {format_rank(raid['mythic']['realm'])}"
                    )
                    await interaction.followup.send(msg)

async def setup(bot):
    await bot.add_cog(RaidProgression(bot))
