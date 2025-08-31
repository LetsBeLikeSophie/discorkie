import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# .env에서 토큰 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 서버 제한 설정
GUILD_ID = 1275099769731022971  # 우당탕탕 스톰윈드 지구대 서버 ID

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # /권한정리 등에서 필요!

# 봇 인스턴스
bot = commands.Bot(command_prefix="!", intents=intents)

# 글로벌 서버 체크 함수
async def guild_only_check(interaction):
    if interaction.guild is None or interaction.guild.id != GUILD_ID:
        await interaction.response.send_message(
            "❌ 이 명령어는 우당탕탕 스톰윈드 지구대에서만 사용할 수 있어요!", 
            ephemeral=True
        )
        return False
    return True

@bot.event
async def on_ready():
    await bot.tree.sync()  # 명령어 동기화
    await bot.change_presence(activity=discord.Game("우당탕탕 명령어 실행"))
    print(f">>> {bot.user} 봇이 로그인했어요!")
    print(f">>> 서버 제한: {GUILD_ID} (우당탕탕 스톰윈드 지구대)")

@bot.event
async def on_interaction(interaction):
    # 슬래시 명령어에 대해서만 서버 체크
    if interaction.type == discord.InteractionType.application_command:
        # 서버 체크 실패시 여기서 차단
        if not await guild_only_check(interaction):
            return
    
    # 정상적인 명령어 처리 계속 (이 부분이 중요!)
    # 원래 discord.py가 처리하도록 넘김
    bot.dispatch('interaction', interaction)

# 코그 로드
@bot.event
async def setup_hook():
    await bot.load_extension("cogs.raid")
    await bot.load_extension("cogs.wow")  
    await bot.load_extension("cogs.raider") 
    await bot.load_extension("cogs.wowinfo") 
    await bot.load_extension("cogs.stat") 
    await bot.load_extension("cogs.craft") 
    await bot.load_extension("cogs.level_scan") 
    await bot.load_extension("cogs.general")

# 봇 실행
bot.run(TOKEN)
