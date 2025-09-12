# cogs/raid_system.py
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from db.database_manager import DatabaseManager  # 수정
from datetime import datetime, timedelta
import pytz

class RaidSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()  # 수정

    async def cog_load(self):
        """Cog 로드 시 DB 연결"""
        await self.db_manager.create_pool()
        print(">>> RaidSystem: 데이터베이스 연결 완료")

    async def cog_unload(self):
        """Cog 언로드 시 DB 연결 해제"""  
        await self.db_manager.close_pool()
        print(">>> RaidSystem: 데이터베이스 연결 해제")

    @app_commands.command(name="일정조회", description="예정된 레이드 일정을 조회합니다")
    async def show_schedule(self, interaction: Interaction):
        await interaction.response.defer()
        
        try:
            # DB 쿼리 방식 수정
            async with self.db_manager.get_connection() as conn:
                events = await conn.fetch("""
                    SELECT event_name, expansion, season, difficulty, content_name,
                           day_of_week, start_time, duration_minutes, max_participants
                    FROM guild_bot.events 
                    WHERE is_active = true 
                    ORDER BY day_of_week, start_time
                """)
            
            if not events:
                await interaction.followup.send("등록된 일정이 없습니다.")
                return
            
            # 요일 매핑
            weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
            
            # 메시지 구성
            embed = discord.Embed(
                title="🗡️ 레이드 일정표",
                description="현재 등록된 레이드 일정들입니다.",
                color=0x0099ff
            )
            
            for event in events:
                day_name = weekdays[event['day_of_week']]
                start_time = str(event['start_time'])[:5]  # HH:MM만
                duration_hours = event['duration_minutes'] // 60
                
                field_name = f"{event['event_name']} ({day_name}요일)"
                field_value = (
                    f"🕘 **{start_time} ~ {duration_hours}시간**\n"
                    f"🏰 {event['expansion']} S{event['season']} {event['difficulty']}\n"
                    f"📍 {event['content_name']}\n"
                    f"👥 최대 {event['max_participants']}명"
                )
                
                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f">>> 일정조회 오류: {e}")
            await interaction.followup.send("일정 조회 중 오류가 발생했습니다.")



    @app_commands.command(name="일정생성", description="테스트용 일정 인스턴스를 수동으로 생성합니다")
    @commands.has_permissions(administrator=True)
    async def create_event_instance(self, interaction: Interaction, 일정이름: str, 날짜: str):
        """
        사용법: /일정생성 "1st Raid" "2025-09-15"
        """
        await interaction.response.defer()
        
        try:
            # 1. 일정 템플릿 조회
            async with self.db_manager.get_connection() as conn:
                template = await conn.fetchrow("""
                    SELECT * FROM guild_bot.events 
                    WHERE event_name = $1 AND is_active = true
                    LIMIT 1
                """, 일정이름)
                
                if not template:
                    await interaction.followup.send(f"❌ '{일정이름}' 일정 템플릿을 찾을 수 없습니다.")
                    return
                
                # 2. 날짜 파싱
                from datetime import datetime
                try:
                    target_date = datetime.strptime(날짜, "%Y-%m-%d").date()
                    start_datetime = datetime.combine(target_date, template['start_time'])
                except ValueError:
                    await interaction.followup.send("❌ 날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)")
                    return
                
                # 3. 일정 인스턴스 생성
                instance_id = await conn.fetchval("""
                    INSERT INTO guild_bot.event_instances 
                    (event_id, instance_date, instance_datetime, status)
                    VALUES ($1, $2, $3, 'upcoming')
                    RETURNING id
                """, template['id'], target_date, start_datetime)
                
                # 4. 성공 메시지
                weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
                day_name = weekdays[target_date.isoweekday()]
                
                await interaction.followup.send(
                    f"✅ **일정 생성 완료!**\n"
                    f"📅 {template['event_name']} - {target_date} ({day_name})\n"
                    f"🕘 {template['start_time']}\n"
                    f"🆔 인스턴스 ID: {instance_id}"
                )
                
                print(f">>> 일정 인스턴스 생성: ID {instance_id}, {일정이름}, {날짜}")
                
        except Exception as e:
            print(f">>> 일정생성 오류: {e}")
            await interaction.followup.send("❌ 일정 생성 중 오류가 발생했습니다.")

async def setup(bot):
    await bot.add_cog(RaidSystem(bot))