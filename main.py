import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

# .env에서 토큰 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # /권한정리 등에서 필요!

# 봇 인스턴스
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()  # 명령어 동기화
    await bot.change_presence(activity=discord.Game("우당탕탕 명령어 실행"))
    print(f"{bot.user} 봇이 로그인했어요!")


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

# 봇 실행
bot.run(TOKEN)
