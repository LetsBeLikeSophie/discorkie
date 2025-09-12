from discord.ext import commands
from discord import app_commands, Interaction
import discord
import os
from decorators.guild_only import guild_only
from db.database_manager import DatabaseManager

class Raid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()

    async def cog_load(self):
        """코그 로드 시 DB 연결"""
        await self.db_manager.create_pool()
        print(">>> Raid: 데이터베이스 연결 완료")

    async def cog_unload(self):
        """코그 언로드 시 DB 연결 해제"""
        await self.db_manager.close_pool()
        print(">>> Raid: 데이터베이스 연결 해제")

    # /닉 - 단순한 닉네임 변경
    @app_commands.command(name="닉", description="닉네임을 변경해요!")
    @app_commands.describe(new_nickname="바꾸고 싶은 닉네임")
    @guild_only() 
    async def change_nickname(self, interaction: Interaction, new_nickname: str):
        try:
            await interaction.user.edit(nick=new_nickname)
            await interaction.response.send_message(
                f"✅ 닉네임이 **{new_nickname}**로 변경되었어요!",
                ephemeral=True
            )
            print(f">>> 닉네임 변경: {interaction.user.name} -> {new_nickname}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ 권한이 부족해서 닉네임을 변경할 수 없어요!",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                "❌ 닉네임 변경 중 오류가 발생했어요!",
                ephemeral=True
            )
            print(f">>> 닉네임 변경 오류: {e}")

    @app_commands.command(name="심크", description="sim 명령어를 자동 생성해줘요!")
    @app_commands.describe(character_name="캐릭터 이름 (없으면 본인 서버닉네임 사용)")
    @guild_only() 
    async def sim_helper(self, interaction: Interaction, character_name: str = None):
        await interaction.response.defer(ephemeral=True)
        
        # 캐릭터명이 없으면 서버 닉네임 사용 (🚀 제거)
        if not character_name:
            character_name = interaction.user.display_name.replace("🚀", "")

        file_path = "member.txt"
        if not os.path.exists(file_path):
            await interaction.followup.send("💾 member.txt 파일이 없어요!")
            return

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found_server = None
        for line in lines:
            if "-" not in line:
                continue
            name, slug = line.strip().split("-", 1)
            if name == character_name:
                found_server = slug
                break

        if found_server:
            sim_params = f"kr {found_server} {character_name}"
            
            await interaction.followup.send(
                f"**🎮 {character_name}님의 sim 파라미터:**\n\n"
                f"**📋 아래를 복사해서 /sim 뒤에 붙여넣으세요:**\n"
                f"```{sim_params}```\n"
                f"🔍 서버: `{found_server}`"
            )
        else:
            await interaction.followup.send(
                f"❌ **{character_name}** 캐릭터를 찾을 수 없어요 😢\n"
                f"member.txt에 `{character_name}-서버명` 형태로 등록되어 있는지 확인해주세요!"
            )

# Cog 등록
async def setup(bot):
    await bot.add_cog(Raid(bot))