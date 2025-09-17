# cogs/admin/raid_management.py
import discord
from discord import app_commands, Interaction, ui
from discord.ext import commands
from db.database_manager import DatabaseManager
from services.character_service import CharacterService
from services.participation_service import ParticipationService
from utils.wow_translation import translate_realm_en_to_kr, translate_class_en_to_kr, REALM_KR_TO_EN
from utils.wow_role_mapping import get_role_korean
from utils.helpers import Logger, ParticipationStatus
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json
import os


class AdminRaidManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.character_service = CharacterService(self.db_manager)
        self.participation_service = ParticipationService(self.db_manager)

    async def cog_load(self):
        """Cog 로드 시 DB 연결"""
        await self.db_manager.create_pool()
        print(">>> AdminRaidManagement: 데이터베이스 연결 완료")

    async def cog_unload(self):
        """Cog 언로드 시 DB 연결 해제"""
        await self.db_manager.close_pool()
        print(">>> AdminRaidManagement: 데이터베이스 연결 해제")

    async def get_upcoming_events(self) -> List[Dict]:
        """활성 상태인 일정 목록 조회"""
        async with self.db_manager.get_connection() as conn:
            events = await conn.fetch("""
                SELECT ei.id, ei.instance_date, ei.instance_datetime,
                    ei.discord_message_id, ei.discord_channel_id,
                    e.event_name, e.expansion, e.season, e.difficulty,
                    e.content_name, e.max_participants
                FROM guild_bot.event_instances ei
                JOIN guild_bot.events e ON ei.event_id = e.id
                WHERE ei.status NOT IN ('completed', 'cancelled')
                ORDER BY ei.instance_date, ei.instance_datetime
            """)
            
            return [dict(row) for row in events]

    async def get_event_participants(self, event_instance_id: int) -> List[Dict]:
        """특정 일정의 참가자 목록 조회"""
        async with self.db_manager.get_connection() as conn:
            participants = await conn.fetch("""
                SELECT ep.character_id, ep.discord_user_id, ep.character_name, ep.character_realm, ep.character_class,
                       ep.character_spec, ep.detailed_role, ep.participation_status,
                       ep.participant_notes, ep.raid_progression,
                       du.discord_username
                FROM guild_bot.event_participations ep
                JOIN guild_bot.discord_users du ON ep.discord_user_id = du.id
                WHERE ep.event_instance_id = $1
                ORDER BY 
                    CASE ep.participation_status 
                        WHEN 'confirmed' THEN 1 
                        WHEN 'tentative' THEN 2 
                        WHEN 'declined' THEN 3 
                    END,
                    CASE ep.detailed_role 
                        WHEN 'TANK' THEN 1 
                        WHEN 'HEALER' THEN 2 
                        WHEN 'MELEE_DPS' THEN 3 
                        WHEN 'RANGED_DPS' THEN 4 
                    END,
                    ep.character_name
            """, event_instance_id)
            
            return [dict(row) for row in participants]

    @app_commands.command(name="관리자_참가관리", description="관리자가 일정 참가자를 관리합니다")
    @commands.has_permissions(administrator=True)
    async def admin_participant_management(self, interaction: Interaction):
        """관리자용 참가자 관리"""
        await interaction.response.defer()
        
        try:
            events = await self.get_upcoming_events()
            
            if not events:
                await interaction.followup.send(">>> 관리할 활성 일정이 없습니다.")
                return
            
            # 일정 선택 View 생성
            view = EventSelectionView(self, events)
            embed = self.create_event_list_embed(events)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            Logger.error(f"관리자_참가관리 오류: {e}")
            await interaction.followup.send(">>> 오류가 발생했습니다.")

    @app_commands.command(name="관리자_진행도새로고침", description="참가자들의 레이드 진행도를 새로고침합니다")
    @commands.has_permissions(administrator=True)
    async def admin_refresh_progression(self, interaction: Interaction, 인스턴스id: int):
        """참가자들의 진행도 새로고침"""
        await interaction.response.defer()
        
        try:
            # 해당 일정의 참가자 조회
            participants = await self.get_event_participants(인스턴스id)
            
            if not participants:
                await interaction.followup.send(">>> 해당 일정에 참가자가 없습니다.")
                return
            
            # TODO: raid_progression API 업데이트 로직 구현
            # 현재는 메시지만 표시
            await interaction.followup.send(
                f">>> 진행도 새로고침 시작: {len(participants)}명\n"
                ">>> (구현 예정: Raider.io API 호출로 progression 업데이트)"
            )
            
        except Exception as e:
            Logger.error(f"진행도 새로고침 오류: {e}")
            await interaction.followup.send(">>> 진행도 새로고침 중 오류가 발생했습니다.")

    def create_event_list_embed(self, events: List[Dict]) -> discord.Embed:
        """일정 목록 임베드 생성"""
        embed = discord.Embed(
            title="📋 일정 선택",
            description="관리할 일정을 선택해주세요.",
            color=0x0099ff
        )
        
        weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
        
        for event in events[:10]:  # 최대 10개까지만 표시
            date = event['instance_date']
            day_name = weekdays[date.isoweekday()]
            time_str = event['instance_datetime'].strftime('%H:%M')
            
            embed.add_field(
                name=f"{date} ({day_name}) {time_str}",
                value=f"**{event['event_name']}**\n{event['expansion']} S{event['season']} {event['difficulty']}",
                inline=True
            )
        
        return embed

    def create_participants_embed(self, event_data: Dict, participants: List[Dict]) -> discord.Embed:
        """참가자 목록 임베드 생성"""
        weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
        date = event_data['instance_date']
        day_name = weekdays[date.isoweekday()]
        time_str = event_data['instance_datetime'].strftime('%H:%M')
        
        embed = discord.Embed(
            title=f"👥 {event_data['event_name']} 참가자 현황",
            description=f"**{date} ({day_name}) {time_str}**\n{event_data['expansion']} S{event_data['season']} {event_data['difficulty']}",
            color=0x0099ff
        )
        
        # WoW 이모티콘 로드
        wow_emojis = self.load_wow_class_emojis()
        
        # 참가자 상태별 그룹화
        status_groups = {
            'confirmed': [],
            'tentative': [], 
            'declined': []
        }
        
        for participant in participants:
            status_groups[participant['participation_status']].append(participant)
        
        # 역할별 카운팅
        role_counts = self.count_roles(participants)
        
        # 📊 참여 현황 요약
        total_attending = len(status_groups['confirmed']) + len(status_groups['tentative'])
        summary_text = (
            f"**전체**: {total_attending}명 / {event_data['max_participants']}명\n"
            f"확정: {len(status_groups['confirmed'])}명, "
            f"미정: {len(status_groups['tentative'])}명, "
            f"불참: {len(status_groups['declined'])}명\n"
            f"🛡️ 탱커: {role_counts['TANK']}명, "
            f"💚 힐러: {role_counts['HEALER']}명, "
            f"⚔️ 근딜: {role_counts['MELEE_DPS']}명, "
            f"🏹 원딜: {role_counts['RANGED_DPS']}명"
        )
        
        embed.add_field(name="📊 참여 현황", value=summary_text, inline=False)
        
        # 확정 참가자만 역할별로 상세 표시
        if status_groups['confirmed']:
            confirmed_text = self.format_participants_by_role(status_groups['confirmed'], wow_emojis)
            embed.add_field(name="✅ 확정 참가자", value=confirmed_text, inline=False)
        
        # 미정/불참은 간단히
        if status_groups['tentative']:
            tentative_names = [p['character_name'] for p in status_groups['tentative']]
            embed.add_field(name="⏳ 미정", value=", ".join(tentative_names), inline=True)
        
        if status_groups['declined']:
            declined_names = [p['character_name'] for p in status_groups['declined']]
            embed.add_field(name="❌ 불참", value=", ".join(declined_names), inline=True)
        
        return embed

    def load_wow_class_emojis(self) -> Dict[str, str]:
        """WoW 직업 이모티콘 로드"""
        try:
            with open('data/server_emojis.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {k: v['format'] for k, v in data.get('wow_classes', {}).items()}
        except:
            return {}

    def count_roles(self, participants: List[Dict]) -> Dict[str, int]:
        """역할별 인원 카운팅"""
        counts = {'TANK': 0, 'HEALER': 0, 'MELEE_DPS': 0, 'RANGED_DPS': 0}
        for p in participants:
            if p['participation_status'] == 'confirmed':
                role = p['detailed_role'] or 'MELEE_DPS'
                counts[role] = counts.get(role, 0) + 1
        return counts

    def format_participants_by_role(self, participants: List[Dict], wow_emojis: Dict[str, str]) -> str:
        """역할별 참가자 포맷팅"""
        roles = {
            'TANK': ('🛡️', '탱커'),
            'HEALER': ('💚', '힐러'),  
            'MELEE_DPS': ('⚔️', '근딜'),
            'RANGED_DPS': ('🏹', '원딜')
        }
        
        role_groups = {}
        for p in participants:
            role = p['detailed_role'] or 'MELEE_DPS'
            if role not in role_groups:
                role_groups[role] = []
            role_groups[role].append(p)
        
        result_lines = []
        for role_key, (emoji, name) in roles.items():
            if role_key in role_groups:
                result_lines.append(f"\n{emoji} **{name} ({len(role_groups[role_key])}명)**")
                for p in role_groups[role_key]:
                    class_emoji = wow_emojis.get(p['character_class'], '⚪')
                    result_lines.append(f"{class_emoji} {p['character_name']}")
        
        return '\n'.join(result_lines) if result_lines else "참가자가 없습니다."


class EventSelectionView(ui.View):
    def __init__(self, cog: AdminRaidManagement, events: List[Dict]):
        super().__init__(timeout=300)
        self.cog = cog
        self.events = events
        
        # 드롭다운 생성
        self.add_item(EventSelectionDropdown(cog, events))


class EventSelectionDropdown(ui.Select):
    def __init__(self, cog: AdminRaidManagement, events: List[Dict]):
        self.cog = cog
        self.events = events
        
        weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
        options = []
        
        for event in events[:25]:  # Discord 제한
            date = event['instance_date']
            day_name = weekdays[date.isoweekday()]
            time_str = event['instance_datetime'].strftime('%H:%M')
            
            options.append(discord.SelectOption(
                label=f"{date} ({day_name}) {time_str}",
                description=f"{event['event_name']} - {event['expansion']} S{event['season']}",
                value=str(event['id'])
            ))
        
        super().__init__(placeholder="관리할 일정을 선택하세요...", options=options)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        
        event_instance_id = int(self.values[0])
        
        # 선택된 일정 정보
        selected_event = next(e for e in self.events if e['id'] == event_instance_id)
        
        # 참가자 목록 조회
        participants = await self.cog.get_event_participants(event_instance_id)
        
        # 참가자 관리 View와 Embed 생성
        embed = self.cog.create_participants_embed(selected_event, participants)
        view = ParticipantManagementView(self.cog, event_instance_id, participants, selected_event)
        
        await interaction.followup.send(embed=embed, view=view)


class ParticipantManagementView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participants: List[Dict], event_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participants = participants
        self.event_data = event_data

    @ui.button(label="➕ 참가자 추가", style=discord.ButtonStyle.success)
    async def add_participant(self, interaction: Interaction, button: ui.Button):
        """참가자 추가 버튼"""
        modal = AddParticipantModal(self.cog, self.event_instance_id, self.event_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="📝 상태 변경", style=discord.ButtonStyle.primary)
    async def change_status(self, interaction: Interaction, button: ui.Button):
        """참가자 상태 변경 버튼"""
        if not self.participants:
            await interaction.response.send_message(">>> 참가자가 없습니다.", ephemeral=True)
            return
        
        view = StatusChangeView(self.cog, self.event_instance_id, self.participants, self.event_data)
        await interaction.response.send_message(">>> 상태를 변경할 참가자를 선택하세요:", view=view, ephemeral=True)

    @ui.button(label="🗑️ 참가자 제거", style=discord.ButtonStyle.danger)
    async def remove_participant(self, interaction: Interaction, button: ui.Button):
        """참가자 제거 버튼"""
        if not self.participants:
            await interaction.response.send_message(">>> 참가자가 없습니다.", ephemeral=True)
            return
        
        view = RemoveParticipantView(self.cog, self.event_instance_id, self.participants, self.event_data)
        await interaction.response.send_message(">>> 제거할 참가자를 선택하세요:", view=view, ephemeral=True)


class AddParticipantModal(ui.Modal):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, event_data: Dict):
        super().__init__(title="새 참가자 추가")
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.event_data = event_data

    character_name = ui.TextInput(
        label="캐릭터명",
        placeholder="예: 비수긔",
        required=True,
        max_length=50
    )
    
    server_name = ui.TextInput(
        label="서버명", 
        placeholder="예: 아즈샤라, 하이잘, 불타는 군단, 스톰레이지, 굴단",
        required=True,
        max_length=50
    )
    
    admin_memo = ui.TextInput(
        label="관리자 메모",
        placeholder="수동 추가 사유를 입력하세요",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=200
    )

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        character_name = self.character_name.value.strip()
        server_input = self.server_name.value.strip()
        memo = self.admin_memo.value.strip()
        
        try:
            # 서버명 정규화
            server_en = REALM_KR_TO_EN.get(server_input, server_input)
            
            # 캐릭터 유효성 검사
            from utils.character_validator import validate_character, get_character_info
            
            if not await validate_character(server_en, character_name):
                await interaction.followup.send(
                    f">>> 캐릭터를 찾을 수 없습니다: {character_name}-{server_input}\n"
                    f">>> 캐릭터명과 서버명을 다시 확인해주세요."
                )
                return
            
            # 캐릭터 정보 조회
            char_info = await get_character_info(server_en, character_name)
            if not char_info:
                await interaction.followup.send(">>> 캐릭터 정보를 가져올 수 없습니다.")
                return
            
            # 관리자 메모 포맷팅
            formatted_memo = f"*{memo}*" if memo else "*관리자가 수동 추가*"
            
            # DB 트랜잭션으로 참가자 추가
            async with self.cog.db_manager.get_connection() as conn:
                # 캐릭터 정보 저장
                char_result = {
                    "source": "api",
                    "character_info": char_info
                }
                character_data = await self.cog.character_service.save_character_to_db(char_result, conn)
                
                # ===== 새로 추가: 더미 기록 확인 및 처리 =====
                existing_dummy = await conn.fetchrow("""
                    SELECT ep.id, ep.participation_status, ep.detailed_role, du.is_dummy 
                    FROM guild_bot.event_participations ep
                    JOIN guild_bot.discord_users du ON ep.discord_user_id = du.id
                    WHERE ep.event_instance_id = $1 
                    AND ep.character_id = $2 
                    AND du.is_dummy = TRUE
                """, self.event_instance_id, character_data['character_id'])
                
                if existing_dummy:
                    # 이미 더미로 추가된 캐릭터인 경우
                    Logger.info(f"관리자 추가 시 기존 더미 발견: {character_data['character_name']}")
                    
                    # 기존 더미 기록의 메모만 업데이트
                    await conn.execute("""
                        UPDATE guild_bot.event_participations 
                        SET participant_notes = $1, updated_at = NOW()
                        WHERE id = $2
                    """, formatted_memo, existing_dummy['id'])
                    
                    # 로그 기록 (관리자가 더미 메모 업데이트)
                    await conn.execute("""
                        INSERT INTO guild_bot.event_participation_logs
                        (event_instance_id, character_id, discord_user_id, action_type, 
                         old_status, new_status, character_name, character_realm, 
                         character_class, character_spec, detailed_role,
                         discord_message_id, discord_channel_id, user_display_name, participant_memo)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    """, self.event_instance_id, character_data['character_id'], existing_dummy['id'],
                        "admin_updated_existing_dummy", existing_dummy['participation_status'], existing_dummy['participation_status'],
                        character_data['character_name'], character_data['realm_slug'],
                        character_data['character_class'], character_data['character_spec'], 
                        existing_dummy['detailed_role'], 0, 0, f"관리자_{interaction.user.display_name}", formatted_memo)
                    
                    # 성공 메시지 (이미 존재함을 알림)
                    server_kr = translate_realm_en_to_kr(character_data['realm_slug'])
                    role_kr = get_role_korean(existing_dummy['detailed_role'])
                    
                    await interaction.followup.send(
                        f">>> **이미 추가된 캐릭터입니다! 메모만 업데이트했습니다.**\n"
                        f"캐릭터: {character_data['character_name']}-{server_kr}\n"
                        f"직업: {character_data['character_class']}-{character_data['character_spec']}\n"
                        f"역할: {role_kr}\n"
                        f"상태: 확정 참가 (기존)\n"
                        f"메모: {formatted_memo}"
                    )
                    
                    Logger.info(f"관리자가 기존 더미 메모 업데이트: {character_name}-{server_input} by {interaction.user.display_name}")
                    
                    # 메시지 업데이트
                    await self.update_messages_after_change(interaction)
                    return  # 여기서 함수 종료
                
                # ===== 기존 로직 (더미 기록이 없는 경우) =====
                # 더미 사용자 생성 (기존 코드 그대로)
                import time
                dummy_discord_id = f"DUMMY_{character_name}_{server_en}_{int(time.time())}"
                admin_user_id = await conn.fetchval("""
                    INSERT INTO guild_bot.discord_users (discord_id, discord_username, is_dummy)
                    VALUES ($1, $2, TRUE)
                    RETURNING id
                """, dummy_discord_id, f"관리자추가_{character_name}")

                # 참가 정보 추가 (확정 참가로)
                old_participation, detailed_role = await self.cog.participation_service.upsert_participation(
                    self.event_instance_id, admin_user_id, character_data, 
                    ParticipationStatus.CONFIRMED, formatted_memo, 0, 0, conn)
                
                # 관리자 수동 추가 로그
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, 
                     old_status, new_status, character_name, character_realm, 
                     character_class, character_spec, detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """, self.event_instance_id, character_data['character_id'], admin_user_id,
                    "manual_added_by_admin", None, ParticipationStatus.CONFIRMED,
                    character_data['character_name'], character_data['realm_slug'],
                    character_data['character_class'], character_data['character_spec'], detailed_role,
                    0, 0, f"관리자_{interaction.user.display_name}", formatted_memo)
            
            # 성공 메시지 (새로 추가된 경우)
            server_kr = translate_realm_en_to_kr(character_data['realm_slug'])
            role_kr = get_role_korean(detailed_role)
            
            await interaction.followup.send(
                f">>> **참가자 추가 완료!**\n"
                f"캐릭터: {character_data['character_name']}-{server_kr}\n"
                f"직업: {character_data['character_class']}-{character_data['character_spec']}\n"
                f"역할: {role_kr}\n"
                f"상태: 확정 참가\n"
                f"메모: {formatted_memo}"
            )
            
            Logger.info(f"관리자 수동 참가자 추가: {character_name}-{server_input} by {interaction.user.display_name}")
            
            # 메시지 업데이트
            await self.update_messages_after_change(interaction)

        except Exception as e:
            Logger.error(f"참가자 추가 오류: {e}")
            await interaction.followup.send(">>> 참가자 추가 중 오류가 발생했습니다.")

    async def update_messages_after_change(self, interaction):
        """참가자 변경 후 관련 메시지들 업데이트"""
        try:
            print(">>> 메시지 업데이트 시작")
            
            # 1. 현재 참가자 목록 다시 조회
            updated_participants = await self.cog.get_event_participants(self.event_instance_id)
            
            # 2. 관리자용 참가자 목록 메시지 업데이트
            updated_embed = self.cog.create_participants_embed(self.event_data, updated_participants)
            
            # 현재 interaction이 속한 메시지 업데이트 (관리자용 메시지)
            try:
                original_message = await interaction.original_response()
                if original_message:
                    # 새로운 View 생성 (기존 참가자 목록으로)
                    updated_view = ParticipantManagementView(self.cog, self.event_instance_id, updated_participants, self.event_data)
                    await original_message.edit(embed=updated_embed, view=updated_view)
                    print(">>> 관리자용 참가자 목록 메시지 업데이트 완료")
            except Exception as e:
                print(f">>> 관리자용 메시지 업데이트 오류: {e}")
            
            # 3. 일정 공지 메시지 업데이트 (discord_message_id 있는 경우)
            if self.event_data.get('discord_message_id') and self.event_data.get('discord_channel_id'):
                await self.update_event_announcement_message()
                
        except Exception as e:
            print(f">>> 메시지 업데이트 전체 오류: {e}")
    
    async def update_event_announcement_message(self):
        """일정 공지 메시지 업데이트"""
        try:
            # EventSignupView의 update_event_message 로직을 재사용
            from cogs.raid.schedule_ui import EventSignupView
            
            # 가상의 interaction 대신 봇과 채널을 직접 사용
            bot = self.cog.bot
            channel = bot.get_channel(int(self.event_data['discord_channel_id']))
            
            if channel:
                message = await channel.fetch_message(int(self.event_data['discord_message_id']))
                if message:
                    # 새로운 EventSignupView로 메시지 업데이트
                    signup_view = EventSignupView(
                        self.event_instance_id, 
                        self.cog.db_manager, 
                        int(self.event_data['discord_message_id']), 
                        int(self.event_data['discord_channel_id'])
                    )
                    
                    # 메시지 내용 새로고침
                    async with self.cog.db_manager.get_connection() as conn:
                        # 이벤트 기본 정보
                        event_data = await conn.fetchrow("""
                            SELECT ei.*, e.event_name, e.expansion, e.season, e.difficulty, 
                                e.content_name, e.max_participants, e.duration_minutes
                            FROM guild_bot.event_instances ei
                            JOIN guild_bot.events e ON ei.event_id = e.id
                            WHERE ei.id = $1
                        """, self.event_instance_id)
                        
                        # 참여자 목록 조회 - event_instance_id로 조회하도록 수정!
                        participants_data = await conn.fetch("""
                            SELECT character_name, character_class, character_spec, detailed_role,
                                participation_status, participant_notes, armor_type
                            FROM guild_bot.event_participations
                            WHERE event_instance_id = $1
                            ORDER BY 
                                CASE participation_status 
                                    WHEN 'confirmed' THEN 1 
                                    WHEN 'tentative' THEN 2 
                                    WHEN 'declined' THEN 3 
                                END,
                                CASE detailed_role 
                                    WHEN 'TANK' THEN 1 
                                    WHEN 'HEALER' THEN 2 
                                    WHEN 'MELEE_DPS' THEN 3 
                                    WHEN 'RANGED_DPS' THEN 4 
                                END,
                                character_name
                        """, self.event_instance_id)
                        
                        # 최근 참가 이력 조회
                        recent_logs = await conn.fetch("""
                            SELECT action_type, character_name, old_character_name, participant_memo, created_at
                            FROM guild_bot.event_participation_logs
                            WHERE event_instance_id = $1
                            ORDER BY created_at DESC
                            LIMIT 3
                        """, self.event_instance_id)
                    
                    # 새로운 embed 생성
                    updated_embed = signup_view.create_detailed_event_embed(event_data, participants_data, recent_logs)
                    
                    # 메시지 업데이트
                    await message.edit(embed=updated_embed, view=signup_view)
                    print(">>> 일정 공지 메시지 업데이트 완료")
                    
        except Exception as e:
            print(f">>> 일정 공지 메시지 업데이트 오류: {e}")


class StatusChangeView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participants: List[Dict], event_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participants = participants
        self.event_data = event_data
        
        # 참가자 선택 드롭다운
        options = []
        for i, p in enumerate(participants[:25]):  # Discord 제한
            realm_kr = translate_realm_en_to_kr(p['character_realm'])
            status_emoji = {"confirmed": "✅", "tentative": "⏳", "declined": "❌"}
            emoji = status_emoji.get(p['participation_status'], "")
            
            label = f"{emoji} {p['character_name']}-{realm_kr}"
            options.append(discord.SelectOption(
                label=label[:100],  # Discord 제한
                description=f"{p['character_class']} - {p['participation_status']}",
                value=str(p['character_id'])
            ))
        
        if options:
            self.add_item(ParticipantSelectionDropdown(cog, event_instance_id, participants, event_data, "status_change"))


class RemoveParticipantView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participants: List[Dict], event_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participants = participants
        self.event_data = event_data
        
        # 참가자 선택 드롭다운
        options = []
        for p in participants[:25]:  # Discord 제한
            realm_kr = translate_realm_en_to_kr(p['character_realm'])
            status_emoji = {"confirmed": "✅", "tentative": "⏳", "declined": "❌"}
            emoji = status_emoji.get(p['participation_status'], "")
            
            label = f"{emoji} {p['character_name']}-{realm_kr}"
            options.append(discord.SelectOption(
                label=label[:100],  # Discord 제한
                description=f"{p['character_class']} - {p['participation_status']}",
                value=str(p['character_id'])
            ))
        
        if options:
            self.add_item(ParticipantSelectionDropdown(cog, event_instance_id, participants, event_data, "remove"))


class ParticipantSelectionDropdown(ui.Select):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participants: List[Dict], event_data: Dict, action_type: str):
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participants = participants
        self.event_data = event_data
        self.action_type = action_type
        
        options = []
        for p in participants[:25]:  # Discord 제한
            realm_kr = translate_realm_en_to_kr(p['character_realm'])
            status_emoji = {"confirmed": "✅", "tentative": "⏳", "declined": "❌"}
            emoji = status_emoji.get(p['participation_status'], "")
            
            label = f"{emoji} {p['character_name']}-{realm_kr}"
            options.append(discord.SelectOption(
                label=label[:100],  # Discord 제한
                description=f"{p['character_class']} - {p['participation_status']}",
                value=str(p['character_id'])
            ))
        
        placeholder = "상태를 변경할 참가자를 선택하세요..." if action_type == "status_change" else "제거할 참가자를 선택하세요..."
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        character_id = int(self.values[0])
        participant = next(p for p in self.participants if p['character_id'] == character_id)
        
        if self.action_type == "status_change":
            view = StatusChangeButtonView(self.cog, self.event_instance_id, participant, self.event_data)
            await interaction.followup.send(
                f">>> **{participant['character_name']}**의 상태를 변경하세요:",
                view=view
            )
        elif self.action_type == "remove":
            view = RemoveConfirmView(self.cog, self.event_instance_id, participant, self.event_data)
            await interaction.followup.send(
                f">>> **{participant['character_name']}**을(를) 참가자 목록에서 제거하시겠습니까?",
                view=view
            )


class StatusChangeButtonView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participant: Dict, event_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participant = participant
        self.event_data = event_data

    @ui.button(label="✅ 확정", style=discord.ButtonStyle.success)
    async def set_confirmed(self, interaction: Interaction, button: ui.Button):
        await self.change_status(interaction, "confirmed")

    @ui.button(label="⏳ 미정", style=discord.ButtonStyle.secondary)
    async def set_tentative(self, interaction: Interaction, button: ui.Button):
        await self.change_status(interaction, "tentative")

    @ui.button(label="❌ 불참", style=discord.ButtonStyle.danger)
    async def set_declined(self, interaction: Interaction, button: ui.Button):
        await self.change_status(interaction, "declined")

    async def change_status(self, interaction: Interaction, new_status: str):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # DB에서 상태 변경
            async with self.cog.db_manager.get_connection() as conn:
                old_status = self.participant['participation_status']
                
                # 상태 업데이트
                await conn.execute("""
                    UPDATE guild_bot.event_participations 
                    SET participation_status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE event_instance_id = $2 AND character_id = $3
                """, new_status, self.event_instance_id, self.participant['character_id'])
                
                # 로그 기록
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, 
                     old_status, new_status, character_name, character_realm, 
                     character_class, character_spec, detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """, self.event_instance_id, self.participant['character_id'], self.participant['discord_user_id'],
                    f"admin_changed_to_{new_status}", old_status, new_status,
                    self.participant['character_name'], self.participant['character_realm'],
                    self.participant['character_class'], self.participant['character_spec'], 
                    self.participant['detailed_role'], 0, 0, 
                    f"관리자_{interaction.user.display_name}", f"*관리자가 {old_status}에서 {new_status}로 변경*")
            
            status_names = {
                "confirmed": "확정",
                "tentative": "미정", 
                "declined": "불참"
            }
            
            realm_kr = translate_realm_en_to_kr(self.participant['character_realm'])
            await interaction.followup.send(
                f">>> **상태 변경 완료!**\n"
                f"캐릭터: {self.participant['character_name']}-{realm_kr}\n"
                f"{status_names[old_status]} → {status_names[new_status]}"
            )
            
            print(f">>> 관리자 상태 변경: {self.participant['character_name']} {old_status} → {new_status}")
            
        except Exception as e:
            Logger.error(f"상태 변경 오류: {e}")
            await interaction.followup.send(">>> 상태 변경 중 오류가 발생했습니다.")


class RemoveConfirmView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participant: Dict, event_data: Dict):
        super().__init__(timeout=300)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participant = participant
        self.event_data = event_data

    @ui.button(label="✅ 제거 확정", style=discord.ButtonStyle.danger)
    async def confirm_remove(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # DB에서 참가자 제거
            async with self.cog.db_manager.get_connection() as conn:
                # 참가 정보 삭제
                await conn.execute("""
                    DELETE FROM guild_bot.event_participations 
                    WHERE event_instance_id = $1 AND character_id = $2
                """, self.event_instance_id, self.participant['character_id'])
                
                # 제거 로그 기록
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, 
                     old_status, new_status, character_name, character_realm, 
                     character_class, character_spec, detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """, self.event_instance_id, self.participant['character_id'], self.participant['discord_user_id'],
                    "admin_removed", self.participant['participation_status'], None,
                    self.participant['character_name'], self.participant['character_realm'],
                    self.participant['character_class'], self.participant['character_spec'], 
                    self.participant['detailed_role'], 0, 0, 
                    f"관리자_{interaction.user.display_name}", "*관리자가 참가자 목록에서 제거*")
            
            realm_kr = translate_realm_en_to_kr(self.participant['character_realm'])
            await interaction.followup.send(
                f">>> **참가자 제거 완료!**\n"
                f"캐릭터: {self.participant['character_name']}-{realm_kr}"
            )
            
            print(f">>> 관리자 참가자 제거: {self.participant['character_name']}-{self.participant['character_realm']}")
            
        except Exception as e:
            Logger.error(f"참가자 제거 오류: {e}")
            await interaction.followup.send(">>> 참가자 제거 중 오류가 발생했습니다.")

    @ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_remove(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_message(">>> 참가자 제거를 취소했습니다.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AdminRaidManagement(bot))