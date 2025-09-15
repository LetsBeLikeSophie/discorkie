# cogs/raid/schedule_ui.py (리팩토링됨)
import discord
from discord import ui
from db.database_manager import DatabaseManager
from utils.emoji_helper import get_class_emoji
from utils.wow_translation import translate_spec_en_to_kr, translate_class_en_to_kr, translate_realm_en_to_kr
from utils.wow_role_mapping import get_role_korean
from utils.helpers import Logger, handle_interaction_errors, ParticipationStatus, Emojis, clean_nickname
from services.character_service import CharacterService
from services.participation_service import ParticipationService
from collections import defaultdict


class EventSignupView(discord.ui.View):
    def __init__(self, event_instance_id: int, db_manager: DatabaseManager, discord_message_id: int = None, discord_channel_id: int = None):
        super().__init__(timeout=None)
        self.event_instance_id = event_instance_id
        self.db_manager = db_manager
        self.discord_message_id = discord_message_id
        self.discord_channel_id = discord_channel_id
        
        # 서비스 초기화
        self.character_service = CharacterService(db_manager)
        self.participation_service = ParticipationService(db_manager)

    @discord.ui.button(label="참여", style=discord.ButtonStyle.success)
    async def signup_confirmed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.CONFIRMED)

    @discord.ui.button(label="미정", style=discord.ButtonStyle.secondary) 
    async def signup_tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.TENTATIVE)

    @discord.ui.button(label="불참", style=discord.ButtonStyle.danger)
    async def signup_declined(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.DECLINED)

    @discord.ui.button(label="캐릭터변경", style=discord.ButtonStyle.secondary, row=1)
    async def character_change(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CharacterChangeModal(self.event_instance_id, self.db_manager, 
                                   self.discord_message_id, self.discord_channel_id)
        await interaction.response.send_modal(modal)

    async def _handle_signup(self, interaction: discord.Interaction, status: str):
        """참가 신청 처리 - 통합된 로직"""
        if status in [ParticipationStatus.TENTATIVE, ParticipationStatus.DECLINED]:
            modal = ParticipationMemoModal(status, self.event_instance_id, self.db_manager, 
                                         self.discord_message_id, self.discord_channel_id)
            await interaction.response.send_modal(modal)
            return
        
        await interaction.response.defer(ephemeral=True)
        await self._process_participation(interaction, status)

    @handle_interaction_errors
    async def _process_participation(self, interaction: discord.Interaction, status: str, memo: str = None):
        """참가 처리 핵심 로직"""
        clean_name = clean_nickname(interaction.user.display_name)
        Logger.info(f"참가 신청 시작: {clean_name} -> {status}")
        
        # 1. 캐릭터 검증
        char_validation = await self.character_service.validate_and_get_character(clean_name)
        if not char_validation.get("success"):
            error_msg = char_validation["error"]
            if char_validation.get("needs_clarification"):
                error_msg += "\n**캐릭터변경** 버튼을 눌러서 서버를 명시해주세요."
            await interaction.followup.send(f">>> {error_msg}", ephemeral=True)
            return
        
        # 2. DB 트랜잭션으로 모든 작업 처리
        async with self.db_manager.get_connection() as conn:
            # 캐릭터 정보 처리
            character_data = await self.character_service.save_character_to_db(
                char_validation["char_result"], conn)
            
            # DB에 있던 캐릭터인 경우 상세 정보 조회
            if not character_data["character_role"]:
                char_details = await self.character_service.get_character_details(
                    character_data["character_id"], conn)
                character_data.update({
                    "character_role": char_details['active_spec_role'],
                    "character_spec": char_details['active_spec'],
                    "character_class": char_details['class']
                })
            
            # 사용자 및 소유권 처리
            discord_user_id = await self.participation_service.ensure_discord_user(
                str(interaction.user.id), interaction.user.name, conn)
            
            await self.character_service.set_character_ownership(
                discord_user_id, character_data["character_id"], conn)
            
            # 참가 정보 처리
            old_participation, detailed_role = await self.participation_service.upsert_participation(
                self.event_instance_id, discord_user_id, character_data, status, memo,
                self.discord_message_id, self.discord_channel_id, conn)
            
            # 로그 기록
            await self.participation_service.log_participation_action(
                self.event_instance_id, character_data, discord_user_id, old_participation,
                status, detailed_role, self.discord_message_id, self.discord_channel_id,
                interaction.user.display_name, memo, conn)
        
        # 3. 성공 응답
        await self._send_success_message(interaction, character_data, detailed_role, status, memo)
        await self.update_event_message(interaction)
        Logger.info(f"참가 신청 완료: {clean_name} -> {status}")

    async def _send_success_message(self, interaction, character_data, detailed_role, status, memo):
        """성공 메시지 전송"""
        status_emoji = {"confirmed": "", "tentative": "", "declined": ""}
        status_text = {"confirmed": "확정 참여", "tentative": "미정", "declined": "불참"}
        
        spec_kr = translate_spec_en_to_kr(character_data['character_spec'] or '')
        role_kr = get_role_korean(detailed_role)
        memo_text = f"\n사유: {memo}" if memo else ""
        
        await interaction.followup.send(
            f">>> **{status_text[status]}** 처리 완료!\n"
            f"캐릭터: {character_data['character_name']} ({spec_kr})\n"
            f"역할: {role_kr}{memo_text}",
            ephemeral=True
        )

    async def update_event_message(self, interaction):
        """일정 메시지 업데이트"""
        try:
            async with self.db_manager.get_connection() as conn:
                # 이벤트 기본 정보
                event_data = await conn.fetchrow("""
                    SELECT ei.*, e.event_name, e.expansion, e.season, e.difficulty, 
                           e.content_name, e.max_participants, e.duration_minutes
                    FROM guild_bot.event_instances ei
                    JOIN guild_bot.events e ON ei.event_id = e.id
                    WHERE ei.id = $1
                """, self.event_instance_id)
                
                # 참여자 목록 조회
                participants_data = await conn.fetch("""
                    SELECT character_name, character_class, character_spec, detailed_role,
                           participation_status, participant_notes, armor_type
                    FROM guild_bot.event_participations
                    WHERE discord_message_id = $1
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
                """, self.discord_message_id)
            
            embed = self.create_detailed_event_embed(event_data, participants_data)
            original_message = await interaction.original_response()
            await original_message.edit(embed=embed, view=self)
            
            Logger.info(f"메시지 업데이트 완료: {len(participants_data)}명 참여자")
            
        except Exception as e:
            Logger.error(f"메시지 업데이트 오류: {e}", e)

    def create_detailed_event_embed(self, event_data, participants_data) -> discord.Embed:
        """상세한 참여자 목록이 포함된 임베드 생성"""
        weekdays = ['', '월', '화', '수', '목', '금', '토', '일']
        day_name = weekdays[event_data['instance_date'].isoweekday()]
        start_time = event_data['instance_datetime'].strftime('%H:%M')
        duration_hours = event_data['duration_minutes'] // 60
        
        embed = discord.Embed(
            title=f"🗡️ {event_data['event_name']}",
            description=f"**{event_data['expansion']} S{event_data['season']} {event_data['difficulty']}**",
            color=0x0099ff
        )
        
        # 일정 정보
        embed.add_field(
            name="📅 일정 정보",
            value=(
                f"**날짜**: {event_data['instance_date']} ({day_name}요일)\n"
                f"**시간**: {start_time} ~ {duration_hours}시간\n" 
                f"**장소**: {event_data['content_name']}"
            ),
            inline=False
        )
        
        # 참여자 그룹화
        participants_by_status = defaultdict(list)
        for participant in participants_data:
            participants_by_status[participant['participation_status']].append(participant)
        
        # 확정 참여자 목록
        if participants_by_status['confirmed']:
            confirmed_text = self._format_participants_by_role(participants_by_status['confirmed'])
            embed.add_field(
                name=f"**확정 참여 ({len(participants_by_status['confirmed'])}명)**",
                value=confirmed_text,
                inline=False
            )
        
        # 미정/불참 참여자 목록
        for status, emoji, name in [('tentative', '', '미정'), ('declined', '', '불참')]:
            if participants_by_status[status]:
                text = self._format_participants_simple(participants_by_status[status])
                embed.add_field(
                    name=f"**{name} ({len(participants_by_status[status])}명)**",
                    value=text,
                    inline=False
                )
        
        # 전체 요약
        total_attending = len(participants_by_status['confirmed']) + len(participants_by_status['tentative'])
        embed.add_field(
            name="📊 **참여 현황 요약**",
            value=(
                f"**전체**: {total_attending}명 / {event_data['max_participants']}명\n"
                f"확정: {len(participants_by_status['confirmed'])}명, "
                f"미정: {len(participants_by_status['tentative'])}명, "
                f"불참: {len(participants_by_status['declined'])}명"
            ),
            inline=False
        )
        
        embed.set_footer(text="아래 버튼으로 참가 의사를 표시해주세요!")
        return embed

    def _format_participants_by_role(self, participants) -> str:
        """역할별 참여자 포맷팅"""
        roles = defaultdict(list)
        for p in participants:
            role = p['detailed_role'] or 'MELEE_DPS'
            roles[role].append(p)
        
        result_lines = []
        role_data = [
            ('TANK', '🛡️', '탱커'),
            ('HEALER', '💚', '힐러'),
            ('MELEE_DPS', '⚔️', '근딜'),
            ('RANGED_DPS', '🏹', '원딜')
        ]
        
        for role_key, emoji, role_name in role_data:
            if roles[role_key]:
                result_lines.append(f"\n{emoji} **{role_name} ({len(roles[role_key])}명)**")
                for p in roles[role_key]:
                    class_emoji = get_class_emoji(p['character_class'] or 'unknown')
                    spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
                    spec_text = f"({spec_kr})" if spec_kr else ""
                    result_lines.append(f"   • {class_emoji} {p['character_name']}{spec_text}")
        
        return '\n'.join(result_lines) if result_lines else "참여자가 없습니다."

    def _format_participants_simple(self, participants) -> str:
        """단순한 참여자 목록"""
        result_lines = []
        for p in participants:
            class_emoji = get_class_emoji(p['character_class'] or 'unknown')
            spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
            spec_text = f"({spec_kr})" if spec_kr else ""
            
            line = f"   • {class_emoji} {p['character_name']}{spec_text}"
            if p['participant_notes']:
                line += f" - \"{p['participant_notes']}\""
            
            result_lines.append(line)
        
        return 