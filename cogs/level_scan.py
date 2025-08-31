import os
import re
import csv
import discord
from discord import Interaction, app_commands
from discord.ext import commands
import asyncio

CHANNEL_ID = 1275111651493806150
ALLOWED_ID = [
    1111599410594467862,  # 비수긔
    133478670034665473,  # 딸기
    # 추가하고 싶은 다른 사용자 ID들을 여기에 넣으세요 
    # 123456789012345678,  # 다른 사용자 예시
]
DATA_PATH  = os.path.join("data", "levels.csv")
TARGET_ROLE_ID = 1329456061048164454  # 정리할 역할 ID = 기웃대는 주민
# TARGET_ROLE_ID = 1411679460310122536  # 정리할 역할 ID = 테스트용


class LevelScan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="레벨스캔",
        description="일부 사용자만 사용할 수 있어요."
    )
    async def level_scan(self, interaction: Interaction):
        if interaction.user.id not in ALLOWED_ID:  # ← 이 부분이 올바름
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

        print(f">>> 레벨 스캔 완료: {len(latest)}명의 데이터 저장")
        await interaction.followup.send(
            f"✅ 레벨 스캔 완료! `{DATA_PATH}` 에 저장했어요.", ephemeral=True
        )

    @app_commands.command(
        name="기웃정리", 
        description="특정 역할을 가진 멤버들을 서버에서 정리합니다 (관리자 전용)"
    )
    async def kick_cleanup(self, interaction: Interaction):
        if interaction.user.id not in ALLOWED_ID:  # ← 여기도 수정!
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있어요!", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        # 길드와 역할 확인
        guild = interaction.guild
        if not guild:
            return await interaction.followup.send("❌ 길드 정보를 찾을 수 없어요!")
        
        target_role = guild.get_role(TARGET_ROLE_ID)
        if not target_role:
            return await interaction.followup.send("❌ 대상 역할을 찾을 수 없어요!")
        
        # 해당 역할을 가진 멤버들 찾기
        members_to_kick = [member for member in guild.members if target_role in member.roles]
        
        if not members_to_kick:
            return await interaction.followup.send("✅ 정리할 멤버가 없어요!")
        
        # 확인 메시지
        member_list = "\n".join([f"- {member.display_name} ({member.mention})" 
                                for member in members_to_kick[:10]])  # 최대 10명만 표시
        
        confirm_msg = f">>> 정리 대상 확인\n대상 역할: {target_role.name}\n대상 인원: {len(members_to_kick)}명\n\n"
        if len(members_to_kick) <= 10:
            confirm_msg += f"대상 목록:\n{member_list}\n\n"
        else:
            confirm_msg += f"일부 목록:\n{member_list}\n... 외 {len(members_to_kick) - 10}명\n\n"
        
        confirm_msg += "정말로 진행하시겠습니까? (60초 후 자동 취소)"
        
        # 확인 버튼 뷰
        view = ConfirmKickView(members_to_kick, guild.name)
        
        await interaction.followup.send(confirm_msg, view=view, ephemeral=True)

class ConfirmKickView(discord.ui.View):
    def __init__(self, members_to_kick, guild_name):
        super().__init__(timeout=60)
        self.members_to_kick = members_to_kick
        self.guild_name = guild_name
        
    @discord.ui.button(label="✅ 진행", style=discord.ButtonStyle.danger)
    async def confirm_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        success_count = 0
        dm_success_count = 0
        dm_failed_count = 0
        kick_failed_count = 0
        
        farewell_message = f"""안녕하세요! **{self.guild_name}** 길드에서 인사드려요! 👋

길드 정리 작업으로 인해 서버에서 나가시게 되었어요.
언제든지 다시 돌아오시면 환영이에요! 
함께했던 시간 고마웠고, 나중에 또 만나요! 😊

*우당탕탕 스톰윈드 지구대 드림*"""
        
        print(f">>> 기웃정리 시작: {len(self.members_to_kick)}명 대상")
        
        for i, member in enumerate(self.members_to_kick, 1):
            try:
                # 1. DM 발송 시도
                try:
                    await member.send(farewell_message)
                    dm_success_count += 1
                    print(f">>> DM 성공: {member.display_name} ({member.id})")
                except discord.Forbidden:
                    dm_failed_count += 1
                    print(f">>> DM 실패 (차단됨): {member.display_name} ({member.id})")
                except discord.HTTPException as e:
                    dm_failed_count += 1
                    print(f">>> DM 실패 (HTTP오류): {member.display_name} - {e}")
                except Exception as e:
                    dm_failed_count += 1
                    print(f">>> DM 실패 (알 수 없음): {member.display_name} - {e}")
                
                # 2. 잠시 대기 (DM 발송 후 추방까지 시간 간격)
                await asyncio.sleep(1)
                
                # 3. 추방 시도
                try:
                    await member.kick(reason="길드 정리 작업")
                    success_count += 1
                    print(f">>> 추방 성공: {member.display_name} ({member.id})")
                except discord.Forbidden:
                    kick_failed_count += 1
                    print(f">>> 추방 실패 (권한부족): {member.display_name}")
                except discord.HTTPException as e:
                    kick_failed_count += 1
                    print(f">>> 추방 실패 (HTTP오류): {member.display_name} - {e}")
                except Exception as e:
                    kick_failed_count += 1
                    print(f">>> 추방 실패 (알 수 없음): {member.display_name} - {e}")
                
                # 진행상황 업데이트 (5명마다)
                if i % 5 == 0 or i == len(self.members_to_kick):
                    progress_msg = f">>> 진행상황: {i}/{len(self.members_to_kick)} 처리완료"
                    try:
                        await interaction.edit_original_response(content=progress_msg)
                    except:
                        pass
                
                # API 제한 방지를 위한 대기
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f">>> 처리 중 오류 발생: {member.display_name} - {e}")
                continue
        
        # 최종 결과 메시지
        result_msg = f""">>> 기웃정리 완료!

📊 **처리 결과**
- 대상 인원: {len(self.members_to_kick)}명
- 추방 성공: {success_count}명
- 추방 실패: {kick_failed_count}명

💌 **DM 발송 결과** 
- DM 성공: {dm_success_count}명
- DM 실패: {dm_failed_count}명

모든 작업이 완료되었어요!"""

        print(f">>> 기웃정리 최종완료 - 성공:{success_count}, 실패:{kick_failed_count}")
        
        await interaction.edit_original_response(content=result_msg, view=None)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(">>> 기웃정리 취소됨")
        await interaction.response.edit_message(
            content=">>> 기웃정리가 취소되었어요.", 
            view=None
        )
    
    async def on_timeout(self):
        print(">>> 기웃정리 시간초과로 취소")
        # 타임아웃 시 버튼 비활성화
        for item in self.children:
            item.disabled = True

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelScan(bot))