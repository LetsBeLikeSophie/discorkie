import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from db.database_manager import DatabaseManager  # 수정된 import

# .env에서 토큰 불러오기
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # /권한정리 등에서 필요!

# 봇 인스턴스
bot = commands.Bot(command_prefix="!", intents=intents)

# 데이터베이스 매니저 인스턴스 생성
db_manager = DatabaseManager()

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)}개의 슬래시 커맨드를 동기화했습니다.")
        print(f"동기화된 명령어: {[cmd.name for cmd in synced]}")
    except Exception as e:
        print(f"명령어 동기화 실패: {e}")
    
    await bot.change_presence(activity=discord.Game("우당탕탕 명령어 실행"))
    print(f"{bot.user} 봇이 로그인했어요!")

# 코그 로드
@bot.event
async def setup_hook():
    # 데이터베이스 연결 풀 생성
    try:
        await db_manager.create_pool()
        print(">>> 데이터베이스 연결 풀 초기화 완료!")
    except Exception as e:
        print(f">>> 데이터베이스 연결 실패: {e}")
    
    # 코그 로드
    await bot.load_extension("cogs.raid")
    await bot.load_extension("cogs.auto_nickname_handler")  # 자동 닉네임 처리
    await bot.load_extension("cogs.member_manager")
    # await bot.load_extension("cogs.guild_stats")
    await bot.load_extension("services.blizzard.token_price")  
    await bot.load_extension("services.raiderio.affixes") 
    await bot.load_extension("services.wowhead.bis") 
    await bot.load_extension("services.community.secondary_stats") 
    # await bot.load_extension("cogs.craft")  
    # await bot.load_extension("cogs.general")  
    # await bot.load_extension("cogs.raid_schedule")
    # await bot.load_extension("cogs.character_manager")
    # await bot.load_extension("cogs.raid_management")

# 봇 종료 시 데이터베이스 연결 해제
@bot.event  
async def on_disconnect():
    try:
        await db_manager.close_pool()
        print(">>> 데이터베이스 연결 풀 종료")
    except Exception as e:
        print(f">>> 데이터베이스 연결 해제 실패: {e}")

# 봇 실행
bot.run(TOKEN)