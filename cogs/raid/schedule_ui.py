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

    @discord.ui.button(label="참여", style=discord.ButtonStyle.success, custom_id="signup_confirmed")
    async def signup_confirmed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.CONFIRMED)

    @discord.ui.button(label="미정", style=discord.ButtonStyle.secondary, custom_id="signup_tentative") 
    async def signup_tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.TENTATIVE)

    @discord.ui.button(label="불참", style=discord.ButtonStyle.danger, custom_id="signup_declined")
    async def signup_declined(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_signup(interaction, ParticipationStatus.DECLINED)

    @discord.ui.button(label="캐릭터변경", style=discord.ButtonStyle.secondary, row=1, custom_id="character_change")
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
            
            # ===== 새로 추가: 더미 기록 확인 및 처리 =====
            existing_dummy = await conn.fetchrow("""
                SELECT ep.*, du.is_dummy 
                FROM guild_bot.event_participations ep
                JOIN guild_bot.discord_users du ON ep.discord_user_id = du.id
                WHERE ep.event_instance_id = $1 
                AND ep.character_id = $2 
                AND du.is_dummy = TRUE
            """, self.event_instance_id, character_data['character_id'])
            
            if existing_dummy:
                # 더미 기록을 실제 유저로 업데이트
                print(f">>> 더미 기록 발견: {character_data['character_name']}, 실제 유저로 업데이트")
                
                # 실제 사용자 정보 확보
                discord_user_id = await self.participation_service.ensure_discord_user(
                    str(interaction.user.id), interaction.user.name, conn)
                
                # 더미 기록을 실제 유저로 업데이트
                await conn.execute("""
                    UPDATE guild_bot.event_participations 
                    SET discord_user_id = $1, participation_status = $2, participant_notes = $3, updated_at = NOW()
                    WHERE id = $4
                """, discord_user_id, status, memo, existing_dummy['id'])
                
                # 캐릭터 소유권 설정
                await self.character_service.set_character_ownership(
                    discord_user_id, character_data["character_id"], conn)
                
                # 로그 기록 (더미에서 실제 유저로 변경)
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, 
                     old_status, new_status, character_name, character_realm, 
                     character_class, character_spec, detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """, self.event_instance_id, character_data["character_id"], discord_user_id,
                    "dummy_to_real_user", existing_dummy['participation_status'], status,
                    character_data['character_name'], character_data['realm_slug'],
                    character_data['character_class'], character_data['character_spec'], 
                    existing_dummy['detailed_role'], self.discord_message_id, self.discord_channel_id,
                    interaction.user.display_name, memo)
                
                # 특별한 성공 메시지
                await interaction.followup.send(
                    f">>> **관리자가 미리 추가한 캐릭터를 본인 계정으로 연결했습니다!**\n"
                    f"캐릭터: {character_data['character_name']}\n"
                    f"상태: {status}",
                    ephemeral=True
                )
                
                await self.update_event_message(interaction)
                Logger.info(f"더미 기록을 실제 유저로 업데이트 완료: {clean_name} -> {status}")
                return  # 여기서 함수 종료 (기존 로직 실행 안함)
            
            # ===== 기존 로직 (더미 기록이 없는 경우) =====
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
        
        # 3. 성공 응답 - 기존 방식으로 변경
        status_text = {"confirmed": "확정 참여", "tentative": "미정", "declined": "불참"}
        
        spec_kr = translate_spec_en_to_kr(character_data.get('character_spec', ''))
        role_kr = get_role_korean(detailed_role)
        memo_text = f"\n사유: {memo}" if memo else ""
        
        await interaction.followup.send(
            f">>> **{status_text[status]}** 처리 완료!\n"
            f"캐릭터: {character_data['character_name']} ({spec_kr})\n"
            f"역할: {role_kr}{memo_text}",
            ephemeral=True
        )
        
        await self.update_event_message(interaction)
        Logger.info(f"참가 신청 완료: {clean_name} -> {status}")

        
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
            

                # 최근 참가 이력 3개 조회
                recent_logs = await conn.fetch("""
                    SELECT action_type, character_name, old_character_name, participant_memo, created_at
                    FROM guild_bot.event_participation_logs
                    WHERE event_instance_id = $1
                    ORDER BY created_at DESC
                    LIMIT 3
                """, self.event_instance_id)
            
            embed = self.create_detailed_event_embed(event_data, participants_data, recent_logs)
            original_message = await interaction.original_response()
            await original_message.edit(embed=embed, view=self)
            
            Logger.info(f"메시지 업데이트 완료: {len(participants_data)}명 참여자")
            
        except Exception as e:
            Logger.error(f"메시지 업데이트 오류: {e}", e)
            
    def create_detailed_event_embed(self, event_data, participants_data, recent_logs=None) -> discord.Embed:
        """간소화된 참여자 목록과 최근 이력이 포함된 임베드 생성"""
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
        
        # 확정 참여자만 역할별로 표시 (간소화)
        if participants_by_status['confirmed']:
            confirmed_text = self._format_participants_compact(participants_by_status['confirmed'])
            embed.add_field(
                name=f"👥 **참여 인원 ({len(participants_by_status['confirmed'])}명)**",
                value=confirmed_text,
                inline=False
            )
        
        # 간단 요약 (미정/불참 숫자만)
        embed.add_field(
            name="📊 **현황**",
            value=(
                f"**전체**: {len(participants_by_status['confirmed'])}명 / {event_data['max_participants']}명\n"
                f"미정: {len(participants_by_status['tentative'])}명, "
                f"불참: {len(participants_by_status['declined'])}명"
            ),
            inline=False
        )
        
        # 최근 이력 추가 (새로 추가되는 부분)
        if recent_logs:
            embed.add_field(
                name="📝 **최근 이력**",
                value=self._format_recent_logs(recent_logs),
                inline=False
            )
        
        embed.set_footer(text="아래 버튼으로 참가 의사를 표시해주세요!")
        return embed

    def _format_participants_compact(self, participants) -> str:
        """간소화된 역할별 참여자 포맷팅 (아이콘과 특성 포함)"""
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
                    result_lines.append(f"{class_emoji} {p['character_name']}{spec_text}")
        
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
        
        return '\n'.join(result_lines) if result_lines else "해당 없음"
    
    def _format_recent_logs(self, recent_logs) -> str:
        """최근 이력 포맷팅"""
        if not recent_logs:
            return "이력이 없습니다."
        
        result_lines = []
        for log in recent_logs:
            time_str = log['created_at'].strftime('%m/%d %H:%M')
            
            # 캐릭터 변경 액션의 경우 old_character_name 활용
            if log['action_type'].startswith('character_changed_from_'):
                old_char = log.get('old_character_name', '알 수 없음')
                new_char = log['character_name']
                line = f"{time_str} 캐릭터 변경 ({old_char}→{new_char})"
            elif log['action_type'] == 'character_changed_and_joined':
                line = f"{time_str} {log['character_name']} 캐릭터 변경 후 참가"
            else:
                # 일반 액션들 - 캐릭터명 포함
                action_text = {
                    'joined': '참가',
                    'changed_to_confirmed': '확정 변경', 
                    'changed_to_tentative': '미정 변경',
                    'changed_to_declined': '불참 변경'
                }.get(log['action_type'], '변경')
                line = f"{time_str} {log['character_name']} {action_text}"
            
            # 메모가 있으면 추가
            if log['participant_memo']:
                line += f" - \"{log['participant_memo']}\""
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)


class CharacterChangeModal(discord.ui.Modal):
    def __init__(self, event_instance_id: int, db_manager: DatabaseManager, discord_message_id: int, discord_channel_id: int):
        super().__init__(title="캐릭터 변경")
        self.event_instance_id = event_instance_id
        self.db_manager = db_manager
        self.discord_message_id = discord_message_id
        self.discord_channel_id = discord_channel_id
        
        self.character_input = discord.ui.TextInput(
            label="캐릭터명",
            placeholder="예: 비수긔",
            required=True,
            max_length=50
        )
        self.add_item(self.character_input)
        
        self.realm_input = discord.ui.TextInput(
            label="서버명",
            placeholder="예: 아즈샤라, 하이잘, 굴단",
            required=True,
            max_length=50
        )
        self.add_item(self.realm_input)

    @handle_interaction_errors
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        character_name = self.character_input.value.strip()
        realm_input = self.realm_input.value.strip()
        
        Logger.info(f"캐릭터 변경 시도: {character_name}-{realm_input}")
        
        # 서비스 초기화
        character_service = CharacterService(self.db_manager)
        participation_service = ParticipationService(self.db_manager)
        
        # 캐릭터 검증
        char_validation = await character_service.validate_character_from_input(character_name, realm_input)
        if not char_validation.get("success"):
            await interaction.followup.send(f">>> {char_validation['error']}", ephemeral=True)
            return
        
        char_info = char_validation["char_info"]
        realm_name_kr = char_validation["realm_name_kr"]
        
        # 닉네임 변경
        new_nickname = f"{Emojis.ROCKET}{character_name}"
        try:
            await interaction.user.edit(nick=new_nickname)
            Logger.info(f"닉네임 변경 성공: {interaction.user.display_name} -> {new_nickname}")
        except discord.Forbidden:
            Logger.info(f"닉네임 변경 실패 (권한 부족): {interaction.user.name}")
        except Exception as e:
            Logger.error(f"닉네임 변경 오류: {e}")
        
        # DB 트랜잭션으로 모든 작업 처리
        async with self.db_manager.get_connection() as conn:
            # 캐릭터 저장
            character_data = {
                "character_id": None,  # 새로 생성됨
                "character_name": char_info.get("name"),
                "realm_slug": char_info.get("realm"),
                "character_role": char_info.get("active_spec_role"),
                "character_spec": char_info.get("active_spec_name"),
                "character_class": char_info.get("class")
            }
            
            # 캐릭터 DB 저장
            character_data["character_id"] = await conn.fetchval("""
                INSERT INTO guild_bot.characters (
                    character_name, realm_slug, race, class, active_spec, 
                    active_spec_role, gender, faction, achievement_points,
                    profile_url, thumbnail_url, region, last_crawled_at, is_guild_member
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), FALSE)
                ON CONFLICT (character_name, realm_slug) DO UPDATE SET
                    race = EXCLUDED.race,
                    class = EXCLUDED.class,
                    active_spec = EXCLUDED.active_spec,
                    active_spec_role = EXCLUDED.active_spec_role,
                    gender = EXCLUDED.gender,
                    faction = EXCLUDED.faction,
                    achievement_points = EXCLUDED.achievement_points,
                    profile_url = EXCLUDED.profile_url,
                    thumbnail_url = EXCLUDED.thumbnail_url,
                    last_crawled_at = NOW(),
                    updated_at = NOW()
                RETURNING id
            """, char_info.get("name"), char_info.get("realm"), char_info.get("race"),
                char_info.get("class"), char_info.get("active_spec_name"),
                char_info.get("active_spec_role"), char_info.get("gender"),
                char_info.get("faction"), char_info.get("achievement_points", 0),
                char_info.get("profile_url", ""), char_info.get("thumbnail_url", ""), "kr")
            
            # 사용자 및 소유권 처리
            discord_user_id = await participation_service.ensure_discord_user(
                str(interaction.user.id), interaction.user.name, conn)
            
            await character_service.set_character_ownership(
                discord_user_id, character_data["character_id"], conn)
            
            # 자동 참가 (confirmed 상태)
            old_participation, detailed_role = await participation_service.upsert_participation(
                self.event_instance_id, discord_user_id, character_data, 
                ParticipationStatus.CONFIRMED, None, self.discord_message_id, 
                self.discord_channel_id, conn)
            
            # 로그 기록 (캐릭터 변경 특수 액션)
            action_type = "character_changed_and_joined" if not old_participation else f"character_changed_from_{old_participation['participation_status']}"
            await conn.execute("""
                INSERT INTO guild_bot.event_participation_logs
                (event_instance_id, character_id, discord_user_id, action_type, old_status, new_status,
                character_name, character_realm, character_class, character_spec, detailed_role,
                old_character_name, old_detailed_role,
                discord_message_id, discord_channel_id, user_display_name)
                VALUES ($1, $2, $3, $4, $5, 'confirmed', $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            """, self.event_instance_id, character_data["character_id"], discord_user_id, action_type, 
                old_participation['participation_status'] if old_participation else None,
                char_info.get('name'), char_info.get('realm'), char_info.get('class'), 
                char_info.get('active_spec_name'), detailed_role, 
                old_participation['character_name'] if old_participation else None,  # 이 부분이 문제
                old_participation['detailed_role'] if old_participation else None,
                self.discord_message_id, self.discord_channel_id, interaction.user.display_name)
        
        # 성공 메시지
        class_kr = translate_class_en_to_kr(char_info.get("class", ""))
        spec_kr = translate_spec_en_to_kr(char_info.get("active_spec_name", ""))
        role_kr = get_role_korean(detailed_role)
        
        await interaction.followup.send(
            f">>> **캐릭터 변경 및 참가 완료!**\n"
            f"캐릭터: {char_info.get('name')}\n"
            f"서버: {realm_name_kr}\n"
            f"직업: {class_kr} ({spec_kr})\n"
            f"역할: {role_kr}\n"
            f"닉네임: {new_nickname}\n\n"
            f"**확정 참여**로 자동 등록되었습니다!",
            ephemeral=True
        )
        
        # 메시지 업데이트
        signup_view = EventSignupView(self.event_instance_id, self.db_manager, 
                                    self.discord_message_id, self.discord_channel_id)
        await signup_view.update_event_message(interaction)
        
        Logger.info(f"캐릭터 변경 및 참가 완료: {char_info.get('name')}-{char_info.get('realm')}")


class ParticipationMemoModal(discord.ui.Modal):
    def __init__(self, status: str, event_instance_id: int, db_manager: DatabaseManager, discord_message_id: int, discord_channel_id: int):
        super().__init__(title=f"{'미정' if status == 'tentative' else '불참'} 사유 입력")
        self.status = status
        self.event_instance_id = event_instance_id
        self.db_manager = db_manager
        self.discord_message_id = discord_message_id
        self.discord_channel_id = discord_channel_id
        
        self.memo_input = discord.ui.TextInput(
            label="사유를 입력해주세요 (선택사항)",
            placeholder="예: 갑자기 일정이 생겼어요" if status == 'declined' else "예: 시간 확인해보고 답변드릴게요",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.memo_input)

    @handle_interaction_errors
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        memo = self.memo_input.value.strip() if self.memo_input.value else None
        
        # View의 참가 처리 로직 재사용
        signup_view = EventSignupView(self.event_instance_id, self.db_manager, 
                                    self.discord_message_id, self.discord_channel_id)
        await signup_view._process_participation(interaction, self.status, memo)