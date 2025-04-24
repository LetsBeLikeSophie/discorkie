from discord.ext import commands
from discord import Interaction, app_commands
from discord.ui import View, Select
import discord
import aiohttp
from bs4 import BeautifulSoup

# 역할별 전문화 옵션 및 URL 쿼리 매핑
SPEC_OPTIONS = {
    "탱커": ["혈기", "복수", "수호", "양조", "보호", "방어"],
    "딜러": ["암살", "전투", "격노", "사격", "비전", "화염", "암흑", "야성", "조화", "냉기", "파멸"],
    "힐러": ["회복", "보존", "운무", "신성", "수양", "복원"]
}
ROLE_MAPPING = {"탱커": "tanker", "딜러": "dealer", "힐러": "healer"}

class SpecSelect(discord.ui.Select):
    def __init__(self, role: str):
        options = [discord.SelectOption(label=spec, value=spec)
                   for spec in SPEC_OPTIONS.get(role, [])]
        super().__init__(placeholder="전문화를 선택하세요", options=options, min_values=1, max_values=1)
        self.role = role

    async def callback(self, interaction: Interaction):
        spec = self.values[0]
        role = self.role  # "탱커", "딜러", "힐러"
        await interaction.response.defer(ephemeral=True)

        endpoints = {
            "레이드": f"https://wowtat.com/raid/?group={ROLE_MAPPING[role]}",
            "쐐기": f"https://wowtat.com/?group={ROLE_MAPPING[role]}"
        }
        # 엔드포인트별 크롤링 결과를 각각 리스트에 담음
        stats = {"레이드": [], "쐐기": []}
        headers = {"User-Agent": "Mozilla/5.0"}

        async with aiohttp.ClientSession() as session:
            for label, url in endpoints.items():
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"❌ {label} 페이지 접속 실패 😢")
                        return
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    rows = soup.select("table tbody tr")

                    def extract_stat(td):
                        text = td.get_text(strip=True)
                        for key in ["치명", "가속", "특화", "유연"]:
                            text = text.replace(key, "")
                        return text.strip()

                    matched = []
                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) < 5:
                            continue
                        raw_name = cols[0].get_text(separator=" ", strip=True)
                        name = raw_name.replace(" 레이드", "").replace(" TOP 50", "").strip()
                        if name != spec:
                            continue
                        record = {
                            "치명": extract_stat(cols[1]),
                            "가속": extract_stat(cols[2]),
                            "특화": extract_stat(cols[3]),
                            "유연": extract_stat(cols[4])
                        }
                        matched.append(record)
                    stats[label] = matched

        # 딜러 냉기와 힐러 신성인 경우는 하위 전문화가 2개씩 있다고 가정
        ambiguous = False
        sub_titles = None
        if role == "딜러" and spec == "냉기":
            ambiguous = True
            sub_titles = ["죽음의기사", "마법사"]
        elif role == "힐러" and spec == "신성":
            ambiguous = True
            sub_titles = ["성기사", "사제"]

        result = f"🌟 **{spec} 스탯 결과** 🌟\n\n"

        if ambiguous and sub_titles:
            # 각 하위 전문화별로 순서대로 결과 출력
            for i, title in enumerate(sub_titles):
                result += f"**{title}**\n"
                result += " (레이드)  "
                if len(stats["레이드"]) > i:
                    stat = stats["레이드"][i]
                    result += (f"\n\n💖 치명: {stat.get('치명', 'N/A')} / ⚡ 가속: {stat.get('가속', 'N/A')} / "
                               f"🎯 특화: {stat.get('특화', 'N/A')} / 🛡️ 유연: {stat.get('유연', 'N/A')}\n")
                else:
                    result += "데이터 없음\n"
                result += " (쐐기)   "
                if len(stats["쐐기"]) > i:
                    stat = stats["쐐기"][i]
                    result += (f"\n\n💖 치명: {stat.get('치명', 'N/A')} / ⚡ 가속: {stat.get('가속', 'N/A')} / "
                               f"🎯 특화: {stat.get('특화', 'N/A')} / 🛡️ 유연: {stat.get('유연', 'N/A')}\n\n")
                else:
                    result += "데이터 없음\n\n"
        else:
            # 일반 전문화는 첫 번째 결과만 사용
            result += " (레이드)  "
            if stats["레이드"]:
                stat = stats["레이드"][0]
                result += (f"\n💖 치명: {stat.get('치명', 'N/A')} / ⚡ 가속: {stat.get('가속', 'N/A')} / "
                           f"🎯 특화: {stat.get('특화', 'N/A')} / 🛡️ 유연: {stat.get('유연', 'N/A')}\n")
            else:
                result += "데이터 없음\n"
            result += " (쐐기)   "
            if stats["쐐기"]:
                stat = stats["쐐기"][0]
                result += (f"\n💖 치명: {stat.get('치명', 'N/A')} / ⚡ 가속: {stat.get('가속', 'N/A')} / "
                           f"🎯 특화: {stat.get('특화', 'N/A')} / 🛡️ 유연: {stat.get('유연', 'N/A')}\n")
            else:
                result += "데이터 없음\n"
        result += "\n📌 출처: [Wowtat](https://wowtat.com)"
        await interaction.followup.send(result)

class RoleSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=role, value=role)
                   for role in SPEC_OPTIONS.keys()]
        super().__init__(placeholder="역할군을 선택하세요", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: Interaction):
        role = self.values[0]
        view = View()
        view.add_item(SpecSelect(role))
        await interaction.response.send_message(f"🌈 **{role}** 전문화를 선택해주세요~", view=view)

class StatView(View):
    def __init__(self):
        super().__init__()
        self.add_item(RoleSelect())

class Stat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="이차스탯", description="상위50위 평균 2차스탯을 확인해요!")
    async def stat_selector(self, interaction: Interaction):
        await interaction.response.send_message("🧚‍♀️ 역할군을 선택해주세요~", view=StatView())

async def setup(bot: commands.Bot):
    await bot.add_cog(Stat(bot))
