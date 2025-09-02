from discord.ext import commands
from discord import app_commands, Interaction, ForumChannel, ui
import discord
import datetime
import os
import aiohttp
from decorators.guild_only import guild_only

class Raid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /닉
    @app_commands.command(name="닉", description="레이드 참가 캐릭터명으로!")
    @app_commands.describe(new_nickname="바꾸고 싶은 닉네임")
    @guild_only() 
    async def change_nickname(self, interaction: Interaction, new_nickname: str):
        try:
            await interaction.user.edit(nick=new_nickname)
            await interaction.response.send_message(f"히히! 이제부터 **{new_nickname}** 님이에요~ 💕")
        except discord.Forbidden:
            await interaction.response.send_message("앗! 제가 권한이 부족해서 닉네임을 바꿀 수 없어요 😢")
        except Exception:
            await interaction.response.send_message("에러가 발생했어요... 다시 해볼까요? 🫣")

    # /레이드
    @app_commands.command(name="레이드", description="레이드 음성 채널 입장 권한을 받아요!")
    @guild_only() 
    async def give_raid_role(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        role_id = 1300689606672646164
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.followup.send("해당 역할을 찾을 수 없어요 😢")
            return
        if role in interaction.user.roles:
            await interaction.followup.send("이미 레이드 권한이 있어요! 🎧")
            return
        try:
            await interaction.user.add_roles(role)
            await interaction.followup.send("레이드 입장권 드렸어요! ⚔️💕")
        except:
            await interaction.followup.send("역할을 줄 수 없어요. 관리자 권한 확인해주세요!")

    # /권한정리
    @app_commands.command(name="권한정리", description="모든 멤버의 레이드 역할을 제거해요 (관리자 전용)")
    @guild_only() 
    async def clear_raid_roles(self, interaction: Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 명령어는 관리자만 사용할 수 있어요 😣", ephemeral=True)
            return

        await interaction.response.defer()

        role_id = 1300689606672646164
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.followup.send("해당 역할을 찾을 수 없어요 😢")
            return

        removed = []
        failed = []

        async for member in interaction.guild.fetch_members(limit=None):
            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    removed.append(member.display_name)
                except discord.Forbidden:
                    failed.append(f"{member.display_name} (권한 부족)")
                except Exception as e:
                    failed.append(f"{member.display_name} ({str(e)})")

        msg = f"✅ 레이드 역할 제거 완료!\n제거된 멤버: {len(removed)}명\n"
        if removed:
            msg += ", ".join(removed) + "\n"
        if failed:
            msg += f"\n❗ 실패:\n" + "\n".join(failed)

        await interaction.followup.send(msg)

    # # /마지막임베드
    # @app_commands.command(name="마지막임베드", description="포럼에서 봇이 보낸 마지막 임베드를 보여줘요!")
    # async def get_last_embed(self, interaction: Interaction):
    #     await interaction.response.defer(ephemeral=True)
    #     forum_channel_id = 1345937388337365053
    #     target_bot_id = 579155972115660803

    #     forum_channel = interaction.guild.get_channel(forum_channel_id)
    #     if not isinstance(forum_channel, ForumChannel):
    #         await interaction.followup.send("포럼 채널이 아니에요! 😣")
    #         return

    #     threads = forum_channel.threads
    #     for thread in threads:
    #         async for message in thread.history(limit=20):
    #             if message.author.id == target_bot_id and message.embeds:
    #                 await interaction.followup.send(f"`{thread.name}` 스레드에서 찾았어요! 💡", embed=message.embeds[0])
    #                 return

    #     await interaction.followup.send("해당 봇의 임베드 메시지를 찾지 못했어요 😢")

    @app_commands.command(name="심크", description="sim 명령어를 자동 생성해줘요!")
    @app_commands.describe(character_name="캐릭터 이름 (없으면 본인 서버닉네임 사용)")
    @guild_only() 
    async def sim_helper(self, interaction: Interaction, character_name: str = None):
        await interaction.response.defer(ephemeral=True)
        
        # 캐릭터명이 없으면 서버 닉네임 사용
        if not character_name:
            character_name = interaction.user.display_name

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

    @app_commands.command(name="일정", description="예정된 길드 이벤트를 보여줘요!")
    @guild_only() 
    async def show_events(self, interaction: Interaction):
        await interaction.response.defer()

        guild = interaction.guild
        events = await guild.fetch_scheduled_events()
        upcoming = [e for e in events if e.start_time and e.start_time > discord.utils.utcnow()]

        if not upcoming:
            await interaction.followup.send("다가오는 이벤트가 없어요! 💤")
            return

        import pytz
        from datetime import timedelta
        kst = pytz.timezone('Asia/Seoul')
        
        # 현재 한국 시간
        now_kst = discord.utils.utcnow().astimezone(kst)
        today = now_kst.date()
        
        # 다음 목요일 찾기
        current_weekday = today.weekday()  # 월요일=0, 목요일=3
        if current_weekday < 3:  # 월,화,수
            days_until_thursday = 3 - current_weekday
        else:  # 목,금,토,일
            days_until_thursday = 7 - (current_weekday - 3)
        
        next_thursday = today + timedelta(days=days_until_thursday)
        
        # 다음 목요일까지의 일정 필터링
        filtered_events = []
        for event in upcoming:
            event_date = event.start_time.astimezone(kst).date()
            if event_date <= next_thursday:
                filtered_events.append(event)
        
        filtered_events.sort(key=lambda e: e.start_time)
        filtered_events = filtered_events[:4]

        # 상대 날짜 계산 함수
        def get_relative_date(event_date, today):
            diff = (event_date - today).days
            if diff == 0:
                return "오늘"
            elif diff == 1:
                return "내일"
            elif diff == 2:
                return "모레"
            else:
                return f"{diff}일 후"

        # 메시지 구성
        msg = f"**📅 다가오는 목요일 전까지 일정**\n\n"
        
        if filtered_events:
            for i, event in enumerate(filtered_events):
                dt = event.start_time.astimezone(kst)
                event_date = dt.date()
                
                # 상대 날짜와 시간
                relative_date = get_relative_date(event_date, today)
                time_str = dt.strftime("%H:%M")
                
                # 요일 계산 수정 (월요일=0이므로 그대로 사용)
                weekdays = ['월', '화', '수', '목', '금', '토', '일']
                weekday = weekdays[event_date.weekday()]
                
                msg += f"{i+1}. **{relative_date} ({weekday}) {time_str}** - {event.name}\n"
        else:
            msg += "예정된 일정이 없어요! 💤"

        view = ui.View()

        # 레이드 채팅방 버튼 (꾸미기)
        raid_button = ui.Button(
            label="⚔️ 레이드 채팅방 입장", 
            style=discord.ButtonStyle.primary,  # 파란색
            emoji="🎮",
            url="https://discord.com/channels/1275099769731022971/1345938832658534511"
        )
        view.add_item(raid_button)

        await interaction.followup.send(msg, view=view)


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



# Cog 등록
async def setup(bot):
    await bot.add_cog(Raid(bot))
