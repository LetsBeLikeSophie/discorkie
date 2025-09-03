from discord.ext import commands
from discord import app_commands, Interaction
import os
import aiohttp
import datetime
from dotenv import load_dotenv

load_dotenv()

class TokenPrice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_blizzard_token(self):
        client_id = os.getenv("BLIZZARD_CLIENT_ID")
        client_secret = os.getenv("BLIZZARD_CLIENT_SECRET")

        token_url = "https://oauth.battle.net/token"
        auth = aiohttp.BasicAuth(client_id, client_secret)
        data = {"grant_type": "client_credentials"}

        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=data, auth=auth) as resp:
                if resp.status == 200:
                    token_data = await resp.json()
                    return token_data["access_token"]
                else:
                    print(f"토큰 요청 실패: {resp.status}")
                    return None

    @commands.Cog.listener()
    async def on_ready(self):
        print(">>> TokenPrice 기능 준비 완료!")


            
    @app_commands.command(name="토큰", description="현재 와우 토큰 시세를 알려줘요!")
    async def wow_token(self, interaction: Interaction):
        await interaction.response.defer()

        token = await self.get_blizzard_token()
        if token is None:
            await interaction.followup.send("Blizzard 인증에 실패했어요 😢")
            return

        url = "https://kr.api.blizzard.com/data/wow/token/index?namespace=dynamic-kr&locale=ko_KR"
        headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"토큰 정보를 불러오지 못했어요 😢 (상태 코드: {resp.status})")
                    return

                data = await resp.json()
                raw_price = data.get("price")
                timestamp = data.get("last_updated_timestamp")
                dt = datetime.datetime.fromtimestamp(timestamp / 1000)
                relative = get_relative_time(dt)

                if not raw_price or not timestamp:
                    await interaction.followup.send("토큰 정보가 비어있어요 😢")
                    return

                price = raw_price // 10000  # 뒤에 4자리 제거
                time_str = datetime.datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M")

                await interaction.followup.send(
                f"💰 **현재 와우 토큰 시세**: {price:,} 골드\n"
                f"⏰ 마지막 갱신: {relative}"
            )


## 시간변환 함수 eg. 1일전
def get_relative_time(dt: datetime.datetime) -> str:
    now = datetime.datetime.utcnow()
    diff = now - dt

    if diff.total_seconds() < 60:
        return "방금 전"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() // 60)
        return f"{minutes}분 전"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() // 3600)
        return f"{hours}시간 전"
    else:
        days = int(diff.total_seconds() // 86400)
        return f"{days}일 전"



# Cog 등록
async def setup(bot):
    await bot.add_cog(TokenPrice(bot))
