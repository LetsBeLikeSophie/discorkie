import discord
from discord.ext import commands
from discord import app_commands, Interaction
from datetime import datetime, timedelta
from typing import List, Dict, Any
from db.database_manager import db  

# 허용된 사용자 ID 목록
ALLOWED_IDS = [
    1111599410594467862,  # 비수긔
    # 필요시 추가 ID들...
]

class RaidManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_allowed_user(self, user_id: int) -> bool:
        """허용된 사용자인지 확인"""
        return user_id in ALLOWED_IDS

    def get_next_weekdays_until_wednesday(self) -> List[int]:
        """오늘부터 다음 수요일 자정까지의 요일 목록 반환"""
        today = datetime.now()
        current_weekday = today.isoweekday()  # 1=월요일, 7=일요일
        
        weekdays = []
        days_to_check = 0
        
        # 오늘부터 시작해서 다음 주 수요일까지 체크
        while days_to_check < 14:  # 최대 2주까지만 체크
            check_date = today + timedelta(days=days_to_check)
            check_weekday = check_date.isoweekday()
            
            # 수요일(3) 다음날(목요일)이 되면 중단
            if days_to_check > 0 and check_weekday == 4:  # 목요일
                break
                
            if check_weekday not in weekdays:
                weekdays.append(check_weekday)
            
            days_to_check += 1
            
        return sorted(weekdays)

    def calculate_event_date(self, target_weekday: int) -> datetime:
        """다음 해당 요일의 날짜 계산"""
        today = datetime.now()
        current_weekday = today.isoweekday()
        
        # 오늘이 목표 요일보다 이전이면 이번 주, 같거나 이후면 다음 주
        if current_weekday <= target_weekday:
            days_ahead = target_weekday - current_weekday
        else:
            days_ahead = target_weekday + 7 - current_weekday
            
        return today + timedelta(days=days_ahead)

    async def get_available_events(self, weekdays: List[int]) -> List[Dict[str, Any]]:
        """해당 요일들의 이벤트 조회"""
        if not weekdays:
            return []
        
        # weekdays를 placeholders로 변환
        placeholders = ','.join(f'${i+1}' for i in range(len(weekdays)))
        query = f"""
            SELECT * FROM events 
            WHERE day_of_week IN ({placeholders})
            AND status = 'active'
            ORDER BY day_of_week, start_time
        """
        
        events = await db.fetch_all(query, *weekdays)
        return events

    @app_commands.command(name="레이드생성", description="레이드 일정을 생성합니다")
    async def create_raid(self, interaction: Interaction):
        # 권한 확인
        if not self.is_allowed_user(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 레이드 관리자만 사용할 수 있습니다!", 
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 오늘부터 다음 수요일까지의 요일 계산
            target_weekdays = self.get_next_weekdays_until_wednesday()
            print(f">>> 대상 요일들: {target_weekdays}")

            # 해당 요일들의 이벤트 조회
            available_events = await self.get_available_events(target_weekdays)
            
            if not available_events:
                await interaction.followup.send(
                    "📅 생성 가능한 레이드 일정이 없습니다.\n"
                    "새로운 일정 템플릿을 먼저 등록해주세요."
                )
                return

            # 요일 이름 매핑
            weekday_names = {
                1: "월요일", 2: "화요일", 3: "수요일", 4: "목요일",
                5: "금요일", 6: "토요일", 7: "일요일"
            }

            # 이벤트 목록을 선택할 수 있는 View 생성
            view = RaidCreationView(available_events, weekday_names)
            
            await interaction.followup.send(
                "🗡️ **레이드 일정 생성**\n어떤 일정을 생성하시겠습니까?", 
                view=view
            )
            
        except Exception as e:
            print(f">>> 레이드 생성 명령어 오류: {e}")
            await interaction.followup.send("❌ 레이드 일정 조회 중 오류가 발생했습니다.")


class RaidCreationView(discord.ui.View):
    def __init__(self, events: List[Dict[str, Any]], weekday_names: Dict[int, str]):
        super().__init__(timeout=300)  # 5분 타임아웃
        self.events = events
        self.weekday_names = weekday_names
        
        # 선택 옵션 생성
        options = []
        for event in events:
            event_date = self.calculate_event_date(event['day_of_week'])
            date_str = event_date.strftime("%m/%d")
            weekday_name = weekday_names[event['day_of_week']]
            time_str = str(event['start_time'])[:5]  # HH:MM만 표시
            
            option_label = f"{event['event_name']} ({weekday_name} {time_str})"
            option_description = f"{date_str} - {event['raid_title'] or '레이드'}"
            
            options.append(discord.SelectOption(
                label=option_label[:100],  # Discord 제한
                description=option_description[:100],
                value=str(event['id'])
            ))
        
        self.select = discord.ui.Select(
            placeholder="생성할 레이드 일정을 선택하세요...",
            options=options
        )
        self.select.callback = self.on_select
        self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        selected_event_id = int(self.select.values[0])
        selected_event = next(e for e in self.events if e['id'] == selected_event_id)
        
        await interaction.response.defer()
        
        try:
            # 실제 레이드 일정 생성
            await self.create_actual_raid_event(interaction, selected_event)
            
        except Exception as e:
            print(f">>> 레이드 이벤트 생성 오류: {e}")
            await interaction.followup.send("❌ 레이드 일정 생성 중 오류가 발생했습니다.")

    async def create_actual_raid_event(self, interaction: discord.Interaction, template_event: Dict[str, Any]):
        """실제 레이드 이벤트 생성"""
        # 날짜 계산
        target_weekday = template_event['day_of_week']
        event_date = self.calculate_event_date(target_weekday)
        
        # 기존 템플릿 이벤트를 UPDATE (실제 레이드로 활성화)
        template_event_id = template_event['id']
        
        await db.execute_query(
            """UPDATE events 
               SET event_date = $1, 
                   status = 'recruiting',
                   creator_discord_id = $2,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = $3""",
            event_date.date(),
            str(interaction.user.id),
            template_event_id
        )
        
        # 업데이트된 이벤트 정보 다시 조회
        updated_event = await db.fetch_one(
            "SELECT * FROM events WHERE id = $1", 
            template_event_id
        )
        
        # 레이드 신청 메시지 생성
        embed = discord.Embed(
            title=f"🗡️ {updated_event['event_name']}",
            description=f"**{updated_event['raid_title']}**\n\n"
                       f"📅 날짜: {event_date.strftime('%Y년 %m월 %d일')} ({self.weekday_names[target_weekday]})\n"
                       f"⏰ 시간: {str(updated_event['start_time'])[:5]}\n"
                       f"👥 최대 인원: {updated_event['max_participants']}명\n\n"
                       f"{updated_event['description'] or ''}",
            color=0x0099ff
        )
        
        # 신청 버튼 추가
        raid_view = RaidSignupView(template_event_id)
        
        # 실제 채널에 메시지 발송 (여기서는 현재 채널에 발송)
        message = await interaction.followup.send(embed=embed, view=raid_view)
        
        # Discord 메시지 정보를 데이터베이스에 업데이트
        await db.execute_query(
            "UPDATE events SET discord_message_id = $1, discord_channel_id = $2 WHERE id = $3",
            str(message.id),
            str(interaction.channel.id),
            template_event_id
        )
        
        print(f">>> 레이드 일정 활성화 완료: ID {template_event_id}")

    def calculate_event_date(self, target_weekday: int) -> datetime:
        """다음 해당 요일의 날짜 계산"""
        today = datetime.now()
        current_weekday = today.isoweekday()
        
        if current_weekday <= target_weekday:
            days_ahead = target_weekday - current_weekday
        else:
            days_ahead = target_weekday + 7 - current_weekday
            
        return today + timedelta(days=days_ahead)


class RaidSignupView(discord.ui.View):
    """레이드 신청 버튼 View"""
    def __init__(self, event_id: int):
        super().__init__(timeout=None)  # 영구적
        self.event_id = event_id

    @discord.ui.button(label="⚔️ 신청", style=discord.ButtonStyle.primary)
    async def signup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("신청 기능은 아직 구현 중입니다!", ephemeral=True)

    @discord.ui.button(label="❌ 신청취소", style=discord.ButtonStyle.danger)  
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("신청취소 기능은 아직 구현 중입니다!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RaidManagement(bot))