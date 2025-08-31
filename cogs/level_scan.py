import os
import re
import csv
import discord
from discord import Interaction, app_commands
from discord.ext import commands

CHANNEL_ID = 1275111651493806150
ALLOWED_ID = [
    1111599410594467862,  # 비수긔
    133478670034665473,  # 딸기
    # 추가하고 싶은 다른 사용자 ID들을 여기에 넣으세요 
    # 123456789012345678,  # 다른 사용자 예시
]
DATA_PATH  = os.path.join("data", "levels.csv")

class LevelScan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="레벨스캔",
        description="일부 사용자만 사용할 수 있어요."
    )
    async def level_scan(self, interaction: Interaction):
        if interaction.user.id not in ALLOWED_ID:
            return await interaction.response.send_message(
                "❌ 이 명령어는 몇몇 사용자만 사용할 수 있어요!", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            return await interaction.followup.send("⚠️ 채널을 찾을 수 없어요.", ephemeral=True)

        pattern = re.compile(
            r"🥳축하합니다!\s+<@!?(?P<id>\d+)>님!\s*(?P<level>\d+)\s*레벨이 되었습니다\.🎉"
        )
        latest = {}  # user_id -> (nickname, level, timestamp)

        async for msg in channel.history(limit=None):
            m = pattern.search(msg.content)
            if not m or not msg.mentions:
                continue

            member   = msg.mentions[0]
            # 1) 닉네임에 콤마를 슬래시로 치환
            nickname = member.display_name.strip().replace(",", "/")
            level    = m.group("level")
            timestamp= msg.created_at
            user_id  = member.id

            if user_id not in latest:
                latest[user_id] = (nickname, level, timestamp)

        # CSV 저장 (직접 쓰기 방식)
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            # 헤더
            f.write("서버닉네임,디스코드아이디,레벨,메시지 날짜\n")

            for uid, (nick, lvl, dt) in latest.items():
                # 닉네임이 빈 문자열이면 건너뛰기
                if not nick:
                    continue

                # 날짜를 YYYY-MM-DD 형식으로
                date_str = dt.strftime("%Y-%m-%d")
                # 직접 포맷팅: nick 에 콤마가 있어도 그냥 그대로 넣음
                f.write(f"{nick},{uid},{lvl},{date_str}\n")

        await interaction.followup.send(
            f"✅ 레벨 스캔 완료! `{DATA_PATH}` 에 저장했어요.", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelScan(bot))
