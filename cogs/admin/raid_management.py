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
                ORDER BY ei.instance_datetime
            """)
            return events

    def load_wow_class_emojis(self) -> Dict:
        """WoW 직업 이모티콘 로드"""
        try:
            data_path = os.path.join('data', 'server_emojis.json')
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('wow_classes', {})
        except Exception as e:
            Logger.error(f"WoW 이모티콘 로드 실패: {e}")
            return {}

    def get_class_emoji(self, class_name: str, wow_emojis: Dict) -> str:
        """직업명으로 이모티콘 반환"""
        class_lower = class_name.lower()
        
        # 직업명 매핑 (한글 → 영문)
        class_mapping = {
            '전사': 'warrior',
            '성기사': 'paladin', 
            '사냥꾼': 'hunter',
            '도적': 'rogue',
            '사제': 'priest',
            '주술사': 'shaman',
            '법사': 'mage',
            '흑마법사': 'warlock',
            '수도사': 'monk',
            '드루이드': 'druid',
            '악마사냥꾼': 'demonhunter',
            '죽음의기사': 'deathknight',
            '기원사': 'evoker'
        }
        
        # 한글명이면 영문으로 변환
        english_class = class_mapping.get(class_name, class_lower)
        
        # 영문명으로 이모티콘 찾기
        for class_key, emoji_data in wow_emojis.items():
            if english_class == class_key or english_class in class_key:
                return emoji_data['format']
        
        return '⚔️'  # 기본 이모티콘

    def get_role_emoji(self, detailed_role: str) -> str:
        """역할 이모티콘 반환"""
        role_emojis = {
            'TANK': '🛡️',
            'HEALER': '💚',
            'MELEE_DPS': '⚔️',
            'RANGED_DPS': '🏹'
        }
        return role_emojis.get(detailed_role, '⚔️')

    def count_roles(self, participants: List[Dict]) -> Dict:
        """확정 참가자의 역할별 인원수 카운트"""
        role_counts = {'TANK': 0, 'HEALER': 0, 'MELEE_DPS': 0, 'RANGED_DPS': 0}
        
        for p in participants:
            if p['participation_status'] == 'confirmed':
                role = p.get('detailed_role', '')
                if role in role_counts:
                    role_counts[role] += 1
        
        return role_counts

    def get_missing_classes(self, participants: List[Dict], wow_emojis: Dict) -> List[str]:
        """참가자에 없는 직업들의 이모티콘 목록 반환"""
        # 현재 참가자들의 직업 수집
        participant_classes = set()
        for p in participants:
            if p.get('character_class'):
                class_name = p['character_class'].lower()
                # 한글 → 영문 변환
                class_mapping = {
                    '전사': 'warrior', '성기사': 'paladin', '사냥꾼': 'hunter',
                    '도적': 'rogue', '사제': 'priest', '주술사': 'shaman',
                    '법사': 'mage', '흑마법사': 'warlock', '수도사': 'monk',
                    '드루이드': 'druid', '악마사냥꾼': 'demonhunter', 
                    '죽음의기사': 'deathknight', '기원사': 'evoker'
                }
                english_class = class_mapping.get(p['character_class'], class_name)
                participant_classes.add(english_class)
        
        # 모든 직업에서 참가자 직업 제외
        all_classes = set(wow_emojis.keys())
        missing_classes = all_classes - participant_classes
        
        # 이모티콘 포맷으로 변환
        missing_emojis = []
        for class_name in sorted(missing_classes):
            if class_name in wow_emojis:
                missing_emojis.append(wow_emojis[class_name]['format'])
        
        return missing_emojis

    async def get_event_participants(self, event_instance_id: int) -> List[Dict]:
        """일정 참가자 목록 조회"""
        async with self.db_manager.get_connection() as conn:
            participants = await conn.fetch("""
                SELECT ep.character_name, ep.character_realm, ep.character_class,
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
            return participants

    @app_commands.command(name="관리자_참가관리", description="일정 참가자를 관리합니다 (관리자 전용)")
    @app_commands.default_permissions(administrator=True)
    async def manage_participation(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 다가오는 일정 조회
            events = await self.get_upcoming_events()
            
            if not events:
                await interaction.followup.send(">>> 관리할 일정이 없습니다.")
                return
            
            # 일정 선택 View 생성
            view = EventSelectionView(self, events)
            embed = self.create_event_list_embed(events)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            Logger.error(f"관리자_참가관리 오류: {e}")
            await interaction.followup.send(">>> 오류가 발생했습니다.")

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
        
        # 📊 참여 현황 요약 (일정 정보 바로 다음)
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
        
        embed.add_field(
            name="📊 **참여 현황 요약**",
            value=summary_text,
            inline=False
        )
        
        # 확정 참여자
        if status_groups['confirmed']:
            confirmed_text = ""
            for p in status_groups['confirmed']:
                realm_kr = translate_realm_en_to_kr(p['character_realm'])
                class_emoji = self.get_class_emoji(p['character_class'], wow_emojis)
                role_emoji = self.get_role_emoji(p['detailed_role'])
                
                # raid_progression 표시 (임시)
                progression = ""
                if p['raid_progression']:
                    progression = " 진행도 있음"  # 임시로 이렇게
                
                # 메모 처리
                memo = ""
                if p['participant_notes'] and p['participant_notes'].startswith('*'):
                    memo = f" {p['participant_notes']}"
                
                # 새 포맷: 직업이모티콘 캐릭터명-서버명 진행도 역할이모티콘
                confirmed_text += f"{class_emoji} {p['character_name']}-{realm_kr}{progression} {role_emoji}{memo}\n"
            
            embed.add_field(
                name="**확정**",
                value=confirmed_text[:1024],
                inline=False
            )
        
        # 미정 참여자
        if status_groups['tentative']:
            tentative_text = ""
            for p in status_groups['tentative']:
                realm_kr = translate_realm_en_to_kr(p['character_realm'])
                class_emoji = self.get_class_emoji(p['character_class'], wow_emojis)
                
                memo = ""
                if p['participant_notes'] and p['participant_notes'].startswith('*'):
                    memo = f" {p['participant_notes']}"
                
                tentative_text += f"{class_emoji} {p['character_name']}-{realm_kr}{memo}\n"
            
            embed.add_field(
                name="**미정**",
                value=tentative_text[:1024],
                inline=False
            )
        
        # 불참
        if status_groups['declined']:
            declined_text = ""
            for p in status_groups['declined']:
                realm_kr = translate_realm_en_to_kr(p['character_realm'])
                class_emoji = self.get_class_emoji(p['character_class'], wow_emojis)
                
                memo = ""
                if p['participant_notes'] and p['participant_notes'].startswith('*'):
                    memo = f" {p['participant_notes']}"
                
                declined_text += f"{class_emoji} {p['character_name']}-{realm_kr}{memo}\n"
            
            embed.add_field(
                name="**불참**",
                value=declined_text[:1024],
                inline=False
            )
        
        # 없는 직업
        missing_emojis = self.get_missing_classes(participants, wow_emojis)
        if missing_emojis:
            missing_text = " ".join(missing_emojis)
            embed.add_field(
                name="**없는 직업**",
                value=missing_text,
                inline=False
            )
        
        return embed


class EventSelectionView(ui.View):
    def __init__(self, cog: AdminRaidManagement, events: List[Dict]):
        super().__init__(timeout=300)
        self.cog = cog
        self.events = events
        
        # 드롭다운 생성
        options = []
        for event in events[:25]:  # Discord 제한: 최대 25개
            date = event['instance_date']
            weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
            day_name = weekdays[date.isoweekday()]
            time_str = event['instance_datetime'].strftime('%H:%M')
            
            label = f"{date} ({day_name}) {time_str} - {event['event_name']}"
            options.append(discord.SelectOption(
                label=label[:100],  # Discord 제한
                value=str(event['id']),
                description=f"{event['expansion']} S{event['season']} {event['difficulty']}"[:100]
            ))
        
        select = EventSelect(self.cog, options)
        self.add_item(select)


class EventSelect(ui.Select):
    def __init__(self, cog: AdminRaidManagement, options: List[discord.SelectOption]):
        super().__init__(placeholder="일정을 선택하세요...", options=options)
        self.cog = cog

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        
        event_instance_id = int(self.values[0])
        
        try:
            # 일정 정보와 참가자 조회
            async with self.cog.db_manager.get_connection() as conn:
                event_data = await conn.fetchrow("""
                    SELECT ei.*, e.event_name, e.expansion, e.season, e.difficulty,
                           e.content_name, e.max_participants
                    FROM guild_bot.event_instances ei
                    JOIN guild_bot.events e ON ei.event_id = e.id
                    WHERE ei.id = $1
                """, event_instance_id)
                
                if not event_data:
                    await interaction.followup.send(">>> 일정을 찾을 수 없습니다.")
                    return
            
            participants = await self.cog.get_event_participants(event_instance_id)
            
            # 참가자 목록 임베드와 관리 버튼들 생성
            embed = self.cog.create_participants_embed(event_data, participants)
            view = ParticipationManagementView(self.cog, event_instance_id, event_data)
            
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception as e:
            Logger.error(f"일정 선택 처리 오류: {e}")
            await interaction.followup.send(">>> 오류가 발생했습니다.")


class ParticipationManagementView(ui.View):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, event_data: Dict):
        super().__init__(timeout=600)
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.event_data = event_data

    @ui.button(label="새 참가자 추가", style=discord.ButtonStyle.success)
    async def add_participant(self, interaction: Interaction, button: ui.Button):
        modal = AddParticipantModal(self.cog, self.event_instance_id, self.event_data)
        await interaction.response.send_modal(modal)

    @ui.button(label="참가자 상태 변경", style=discord.ButtonStyle.primary)
    async def change_status(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        
        # 현재 참가자 목록 조회
        participants = await self.cog.get_event_participants(self.event_instance_id)
        
        if not participants:
            await interaction.followup.send(">>> 참가자가 없습니다.")
            return
        
        view = StatusChangeView(self.cog, self.event_instance_id, participants, self.event_data)
        await interaction.followup.send(">>> 상태를 변경할 참가자를 선택하세요:", view=view, ephemeral=True)

    @ui.button(label="진행도 새로고침", style=discord.ButtonStyle.secondary)
    async def refresh_progression(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()
        
        try:
            participants = await self.cog.get_event_participants(self.event_instance_id)
            
            if not participants:
                await interaction.followup.send(">>> 새로고침할 참가자가 없습니다.")
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
                
                # 더미 discord_user_id 생성 (관리자 추가용)
                admin_user_id = await self.cog.participation_service.ensure_discord_user(
                    f"admin_{interaction.user.id}", f"관리자_{interaction.user.display_name}", conn)
                
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
            
            # 성공 메시지
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
            # 현재 참가자 목록 다시 조회
            updated_participants = await self.cog.get_event_participants(self.event_instance_id)
            updated_embed = self.cog.create_participants_embed(self.event_data, updated_participants)
            
            print(">>> 메시지 업데이트 시작")
                        
        except Exception as e:
            print(f">>> 메시지 업데이트 전체 오류: {e}")


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
            description = f"{p['character_class']} | {p['participation_status']}"
            
            options.append(discord.SelectOption(
                label=label[:100],
                value=str(i),
                description=description[:100]
            ))
        
        select = ParticipantSelect(self.cog, self.event_instance_id, self.participants)
        self.add_item(select)


class ParticipantSelect(ui.Select):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participants: List[Dict]):
        super().__init__(placeholder="상태를 변경할 참가자를 선택하세요...")
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participants = participants

    async def callback(self, interaction: Interaction):
        participant_index = int(self.values[0])
        participant = self.participants[participant_index]
        
        modal = StatusChangeModal(self.cog, self.event_instance_id, participant)
        await interaction.response.send_modal(modal)


class StatusChangeModal(ui.Modal):
    def __init__(self, cog: AdminRaidManagement, event_instance_id: int, participant: Dict):
        super().__init__(title=f"{participant['character_name']} 상태 변경")
        self.cog = cog
        self.event_instance_id = event_instance_id
        self.participant = participant
        
        # 현재 상태 표시
        current_status = {"confirmed": "확정", "tentative": "미정", "declined": "불참"}
        current = current_status.get(participant['participation_status'], participant['participation_status'])
        
        self.status_input.placeholder = f"현재: {current} → 새 상태를 선택하세요"

    status_input = ui.TextInput(
        label="새 상태",
        placeholder="confirmed, tentative, declined 중 하나",
        required=True,
        max_length=20
    )
    
    admin_memo = ui.TextInput(
        label="관리자 메모",
        placeholder="상태 변경 사유를 입력하세요",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=200
    )

    async def on_submit(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        
        new_status = self.status_input.value.strip().lower()
        memo = self.admin_memo.value.strip()
        
        # 상태 유효성 검사
        valid_statuses = ['confirmed', 'tentative', 'declined']
        if new_status not in valid_statuses:
            await interaction.followup.send(
                f">>> 잘못된 상태입니다. 다음 중 하나를 입력하세요: {', '.join(valid_statuses)}"
            )
            return
        
        try:
            # 관리자 메모 포맷팅
            formatted_memo = f"*{memo}*" if memo else f"*관리자가 {new_status}로 변경*"
            
            async with self.cog.db_manager.get_connection() as conn:
                # 참가 상태 업데이트
                await conn.execute("""
                    UPDATE guild_bot.event_participations
                    SET participation_status = $1, participant_notes = $2, updated_at = NOW()
                    WHERE event_instance_id = $3 AND character_name = $4 AND character_realm = $5
                """, new_status, formatted_memo, self.event_instance_id, 
                    self.participant['character_name'], self.participant['character_realm'])
                
                # 변경 로그 기록
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type,
                     old_status, new_status, character_name, character_realm,
                     character_class, character_spec, detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """, self.event_instance_id, 0, 0, "manual_status_change_by_admin",
                    self.participant['participation_status'], new_status,
                    self.participant['character_name'], self.participant['character_realm'],
                    self.participant['character_class'], self.participant['character_spec'],
                    self.participant['detailed_role'], 0, 0,
                    f"관리자_{interaction.user.display_name}", formatted_memo)
            
            # 성공 메시지
            status_names = {"confirmed": "확정 참가", "tentative": "미정", "declined": "불참"}
            old_status_name = status_names.get(self.participant['participation_status'], self.participant['participation_status'])
            new_status_name = status_names.get(new_status, new_status)
            
            realm_kr = translate_realm_en_to_kr(self.participant['character_realm'])
            
            await interaction.followup.send(
                f">>> **상태 변경 완료!**\n"
                f"캐릭터: {self.participant['character_name']}-{realm_kr}\n"
                f"상태: {old_status_name} → {new_status_name}\n"
                f"메모: {formatted_memo}"
            )
            
            Logger.info(f"관리자 상태 변경: {self.participant['character_name']} {old_status_name}→{new_status_name} by {interaction.user.display_name}")
            
        except Exception as e:
            Logger.error(f"상태 변경 오류: {e}")
            await interaction.followup.send(">>> 상태 변경 중 오류가 발생했습니다.")


async def setup(bot):
    await bot.add_cog(AdminRaidManagement(bot))