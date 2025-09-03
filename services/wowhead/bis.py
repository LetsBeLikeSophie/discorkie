import json
from discord import app_commands, Interaction, ui
from discord.ext import commands

class Bis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.wow_classes = self.load_classes()

    def load_classes(self):
        # JSON 파일을 읽어오는 부분
        with open('data/class.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    @app_commands.command(name="비스", description="와우헤드 BIS 페이지로 보내줘요!")
    @app_commands.describe(class_name="예: 죽음의기사, 전사, 드루이드...")
    async def bis_links(self, interaction: Interaction, class_name: str):
        await interaction.response.defer()

        class_name = class_name.replace(" ", "").lower()

        found = None
        for k in self.wow_classes:
            if k.replace(" ", "").lower() == class_name:
                found = self.wow_classes[k]
                readable_name = k
                break

        if not found:
            await interaction.followup.send("해당 클래스를 찾을 수 없어요 😢")
            return

        class_url = found["url"]
        specs = found["specs"]

        # 버튼 뷰 구성
        view = ui.View()
        for label, spec_url in specs.items():
            url = f"https://www.wowhead.com/ko/guide/classes/{class_url}/{spec_url}/bis-gear"
            view.add_item(ui.Button(label=label, url=url))

        await interaction.followup.send(
            f" 📖**{readable_name} BiS 가이드** 전문화를 골라주세요:",
            view=view
        )

async def setup(bot):
    await bot.add_cog(Bis(bot))
