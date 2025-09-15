import discord
from discord.ext import commands
from discord import app_commands, Interaction, ui
from decorators.guild_only import guild_only
from .schedule_ui import EventSignupView
from db.database_manager import DatabaseManager

class Schedule(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()

    async def cog_load(self):
        """Cog 로드 시 DB 연결"""
        await self.db_manager.create_pool()
        print(">>> Schedule: 데이터베이스 연결 완료")

    async def cog_unload(self):
        """Cog 언로드 시 DB 연결 해제"""  
        await self.db_manager.close_pool()
        print(">>> Schedule: 데이터베이스 연결 해제")

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

    @app_commands.command(name="일정공지", description="일정 인스턴스에 대한 참가 신청 메시지를 발송합니다")
    @commands.has_permissions(administrator=True)
    async def post_event_message(self, interaction: Interaction, 인스턴스id: int):
        """
        사용법: /일정공지 1
        """
        await interaction.response.defer()
        
        try:
            # 일정 인스턴스 정보 조회 (템플릿 정보 포함)
            async with self.db_manager.get_connection() as conn:
                event_data = await conn.fetchrow("""
                    SELECT ei.*, e.event_name, e.expansion, e.season, e.difficulty, 
                        e.content_name, e.max_participants, e.duration_minutes
                    FROM guild_bot.event_instances ei
                    JOIN guild_bot.events e ON ei.event_id = e.id
                    WHERE ei.id = $1
                """, 인스턴스id)
                
                if not event_data:
                    await interaction.followup.send(f"❌ 인스턴스 ID {인스턴스id}를 찾을 수 없습니다.")
                    return
                
                # 임베드 메시지 생성
                embed = self.create_event_embed(event_data)
                
                # 먼저 View 없이 메시지 발송
                message = await interaction.followup.send(embed=embed)
                
                # 메시지 ID와 채널 ID를 받은 후 View 생성
                view = EventSignupView(인스턴스id, self.db_manager, message.id, interaction.channel.id)
                
                # View를 추가해서 메시지 수정
                await message.edit(embed=embed, view=view)
                
                # Discord 메시지 ID를 DB에 저장
                await conn.execute("""
                    UPDATE guild_bot.event_instances 
                    SET discord_message_id = $1, discord_channel_id = $2
                    WHERE id = $3
                """, str(message.id), str(interaction.channel.id), 인스턴스id)
                
                print(f">>> 일정 공지 메시지 발송: 인스턴스 {인스턴스id}, 메시지 {message.id}, 채널 {interaction.channel.id}")
                
        except Exception as e:
            print(f">>> 일정공지 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")
            await interaction.followup.send("❌ 일정 공지 발송 중 오류가 발생했습니다.")


    def create_event_embed(self, event_data) -> discord.Embed:
        """일정 공지용 임베드 생성"""
        weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
        day_name = weekdays[event_data['instance_date'].isoweekday()]
        start_time = event_data['instance_datetime'].strftime('%H:%M')
        duration_hours = event_data['duration_minutes'] // 60
        
        embed = discord.Embed(
            title=f"🗡️ {event_data['event_name']}",
            description=f"**{event_data['expansion']} S{event_data['season']} {event_data['difficulty']}**",
            color=0x0099ff
        )
        
        embed.add_field(
            name="📅 일정 정보",
            value=(
                f"**날짜**: {event_data['instance_date']} ({day_name}요일)\n"
                f"**시간**: {start_time} ~ {duration_hours}시간\n" 
                f"**장소**: {event_data['content_name']}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👥 참여 현황",
            value=(
                f"✅ 확정: {event_data['current_confirmed']}명\n"
                f"❓ 미정: {event_data['current_tentative']}명\n"
                f"❌ 불참: {event_data['current_declined']}명\n"
                f"📊 **전체**: {event_data['current_confirmed'] + event_data['current_tentative']}명 / {event_data['max_participants']}명"
            ),
            inline=True
        )
        
        embed.set_footer(text="아래 버튼으로 참가 의사를 표시해주세요!")
        
        return embed

async def setup(bot):
    await bot.add_cog(Schedule(bot))