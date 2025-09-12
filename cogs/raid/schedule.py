import discord
from discord.ext import commands
from discord import app_commands, Interaction, ui
from decorators.guild_only import guild_only

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

async def setup(bot):
    await bot.add_cog(Schedule(bot))
