# cogs/raid/schedule_ui.py
import discord
from discord import ui
from db.database_manager import DatabaseManager
from utils.emoji_helper import get_class_emoji, get_role_emoji, get_status_emoji
from utils.wow_translation import normalize_realm_input, translate_realm_en_to_kr, translate_spec_en_to_kr, translate_class_en_to_kr
from utils.wow_role_mapping import get_character_role, get_character_armor_type, get_role_korean
from collections import defaultdict

class EventSignupView(discord.ui.View):
    def __init__(self, event_instance_id: int, db_manager: DatabaseManager, discord_message_id: int = None, discord_channel_id: int = None):
        super().__init__(timeout=None)  # 영구적
        self.event_instance_id = event_instance_id
        self.db_manager = db_manager
        self.discord_message_id = discord_message_id
        self.discord_channel_id = discord_channel_id

    @discord.ui.button(label="✅ 참여", style=discord.ButtonStyle.success)
    async def signup_confirmed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_signup(interaction, "confirmed")

    @discord.ui.button(label="❓ 미정", style=discord.ButtonStyle.secondary) 
    async def signup_tentative(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_signup(interaction, "tentative")

    @discord.ui.button(label="❌ 불참", style=discord.ButtonStyle.danger)
    async def signup_declined(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_signup(interaction, "declined")

    @discord.ui.button(label="🔄 캐릭터변경", style=discord.ButtonStyle.secondary, row=1)
    async def character_change(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_character_change(interaction)

    async def handle_signup(self, interaction: discord.Interaction, status: str):
        """참가 신청 처리"""
        # 미정/불참인 경우 메모 입력 모달 표시
        if status in ['tentative', 'declined']:
            modal = ParticipationMemoModal(status, self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
            await interaction.response.send_modal(modal)
            return
        
        # 확정 참여인 경우 바로 처리
        await interaction.response.defer(ephemeral=True)
        
        try:
            discord_id = str(interaction.user.id)
            
            # 1. 닉네임에서 캐릭터명 추출 (이모티콘 제거)
            nickname = interaction.user.display_name
            clean_name = nickname.replace("🚀", "").replace("⭐", "").strip()
            
            print(f">>> 참가 신청 시작: {clean_name}")
            
            # 2. 기존 auto_nickname_handler의 로직 사용
            from cogs.core.auto_nickname import AutoNicknameHandler
            
            handler = AutoNicknameHandler(None)  # bot은 None으로 전달 (DB만 사용)
            handler.db_manager = self.db_manager  # 같은 DB 매니저 사용
            
            # 캐릭터 유효성 체크
            char_result = await handler.check_character_validity(clean_name)
            
            if not char_result:
                await interaction.followup.send(
                    f"❌ **캐릭터를 찾을 수 없습니다**\n"
                    f"현재 닉네임: `{clean_name}`\n\n"
                    f"올바른 캐릭터명으로 닉네임을 설정하거나\n"
                    f"**🔄 캐릭터변경** 버튼을 눌러주세요.",
                    ephemeral=True
                )
                return
            
            # 모호한 캐릭터인 경우 (여러 서버에 존재)
            if char_result.get("needs_clarification"):
                await interaction.followup.send(
                    f"❌ **모호한 캐릭터명입니다**\n"
                    f"'{clean_name}' 캐릭터가 여러 서버에 존재합니다.\n"
                    f"**🔄 캐릭터변경** 버튼을 눌러서 서버를 명시해주세요.",
                    ephemeral=True
                )
                return
            
            # 3. 캐릭터 정보 처리 및 참가 신청
            success = await self.process_character_and_signup(char_result, interaction, status)
            
            if success:
                print(f">>> 참가 신청 성공: {clean_name} -> {status}")
            
        except Exception as e:
            print(f">>> 참가 신청 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")
            await interaction.followup.send("❌ 참가 신청 처리 중 오류가 발생했습니다.", ephemeral=True)

    async def handle_character_change(self, interaction: discord.Interaction):
        """캐릭터 변경 처리 - 모달 입력 후 자동 참가"""
        modal = CharacterChangeModal(self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
        await interaction.response.send_modal(modal)

    async def process_character_and_signup(self, char_result, interaction, status):
        """캐릭터 정보 처리 및 참가 신청 통합"""
        try:
            discord_id = str(interaction.user.id)
            
            # 캐릭터 정보 추출
            if char_result["source"] == "db":
                # DB에 이미 있는 캐릭터
                character_id = char_result["character_id"]
                character_name = char_result["character_name"]
                realm_slug = char_result["realm_slug"]
                
                # 캐릭터 정보 조회
                async with self.db_manager.get_connection() as conn:
                    char_info_db = await conn.fetchrow("""
                        SELECT character_name, realm_slug, active_spec_role, active_spec, class
                        FROM guild_bot.characters 
                        WHERE id = $1
                    """, character_id)
                    
                    if not char_info_db:
                        await interaction.followup.send(
                            "❌ 캐릭터 정보를 가져오는데 실패했습니다.",
                            ephemeral=True
                        )
                        return False
                    
                    character_role = char_info_db['active_spec_role']
                    character_spec = char_info_db['active_spec']
                    character_class = char_info_db['class']
                    
            else:
                # API에서 가져온 캐릭터
                char_info = char_result["character_info"]
                character_name = char_info.get("name")
                realm_slug = char_result["realm_slug"]
                character_role = char_info.get("active_spec_role")
                character_spec = char_info.get("active_spec_name")
                character_class = char_info.get("class")
                
                # 캐릭터를 DB에 저장
                async with self.db_manager.get_connection() as conn:
                    character_id = await conn.fetchval("""
                        INSERT INTO guild_bot.characters (
                            character_name, realm_slug, race, class, active_spec, 
                            active_spec_role, gender, faction, achievement_points,
                            profile_url, thumbnail_url, region, last_crawled_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
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
            
            # 세분화된 역할 계산
            detailed_role = get_character_role(character_class, character_spec)
            armor_type = get_character_armor_type(character_class)
            
            # 디스코드 사용자 및 참가 처리
            async with self.db_manager.get_connection() as conn:
                # 디스코드 사용자 정보 확인/생성
                discord_user_id = await conn.fetchval("""
                    INSERT INTO guild_bot.discord_users (discord_id, discord_username)
                    VALUES ($1, $2)
                    ON CONFLICT (discord_id) DO UPDATE SET
                        discord_username = EXCLUDED.discord_username,
                        updated_at = NOW()
                    RETURNING id
                """, discord_id, interaction.user.name)
                
                # 캐릭터 소유권 설정
                await conn.execute("""
                    UPDATE guild_bot.character_ownership 
                    SET is_verified = FALSE, updated_at = NOW()
                    WHERE discord_user_id = $1 AND is_verified = TRUE
                """, discord_user_id)
                
                await conn.execute("""
                    INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (discord_user_id, character_id) DO UPDATE SET
                        is_verified = TRUE,
                        updated_at = NOW()
                """, discord_user_id, character_id)
                
                # 기존 참가 정보 확인
                existing = await conn.fetchrow("""
                    SELECT participation_status, character_name, character_class, character_spec 
                    FROM guild_bot.event_participations
                    WHERE event_instance_id = $1 AND discord_user_id = $2
                """, self.event_instance_id, discord_user_id)
                
                old_status = existing['participation_status'] if existing else None
                old_character_name = existing['character_name'] if existing else None
                old_character_class = existing['character_class'] if existing else None
                old_character_spec = existing['character_spec'] if existing else None
                
                # 참가 정보 업데이트/삽입 (새로운 구조)
                if existing:
                    await conn.execute("""
                        UPDATE guild_bot.event_participations
                        SET participation_status = $1, character_role = $2, detailed_role = $3,
                            character_id = $4, character_name = $5, character_realm = $6,
                            character_class = $7, character_spec = $8, armor_type = $9,
                            participant_notes = NULL, discord_message_id = $10, 
                            discord_channel_id = $11, updated_at = NOW()
                        WHERE event_instance_id = $12 AND discord_user_id = $13
                    """, status, character_role, detailed_role, character_id, character_name, 
                        realm_slug, character_class, character_spec, armor_type,
                        self.discord_message_id, self.discord_channel_id,
                        self.event_instance_id, discord_user_id)
                else:
                    await conn.execute("""
                        INSERT INTO guild_bot.event_participations
                        (event_instance_id, character_id, discord_user_id, participation_status, 
                         character_role, detailed_role, character_name, character_realm,
                         character_class, character_spec, armor_type, discord_message_id, discord_channel_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """, self.event_instance_id, character_id, discord_user_id, status, 
                        character_role, detailed_role, character_name, realm_slug,
                        character_class, character_spec, armor_type, 
                        self.discord_message_id, self.discord_channel_id)
                
                
                # 로그 기록 (확장된 정보 포함)
                action_type = "joined" if not old_status else f"changed_to_{status}"
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, old_status, new_status,
                     character_name, character_realm, character_class, character_spec, detailed_role,
                     old_character_name, old_character_realm, discord_message_id, discord_channel_id, user_display_name)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """, self.event_instance_id, character_id, discord_user_id, action_type, old_status, status,
                    character_name, realm_slug, character_class, character_spec, detailed_role,
                    old_character_name, realm_slug, self.discord_message_id, self.discord_channel_id, 
                    interaction.user.display_name)
                
                # 성공 메시지
                spec_kr = translate_spec_en_to_kr(character_spec or '')
                role_kr = get_role_korean(detailed_role)
                await interaction.followup.send(
                    f"✅ **확정 참여** 처리 완료!\n"
                    f"캐릭터: {character_name} ({spec_kr})\n"
                    f"역할: {role_kr}",
                    ephemeral=True
                )
                
                # 메시지 업데이트
                await self.update_event_message(interaction)
                
                return True
                
        except Exception as e:
            print(f">>> 캐릭터 처리 및 참가 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")
            return False

    async def update_event_message(self, interaction):
        """일정 메시지 업데이트 - 새로운 구조로 조회"""
        try:
            # 업데이트된 데이터 조회 (간소화된 쿼리)
            async with self.db_manager.get_connection() as conn:
                # 이벤트 기본 정보
                event_data = await conn.fetchrow("""
                    SELECT ei.*, e.event_name, e.expansion, e.season, e.difficulty, 
                           e.content_name, e.max_participants, e.duration_minutes
                    FROM guild_bot.event_instances ei
                    JOIN guild_bot.events e ON ei.event_id = e.id
                    WHERE ei.id = $1
                """, self.event_instance_id)
                
                # 참여자 목록 조회 (단일 테이블에서)
                participants_data = await conn.fetch("""
                    SELECT 
                        character_name, character_class, character_spec, detailed_role,
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
            
            # 임베드 재생성
            embed = self.create_detailed_event_embed(event_data, participants_data)
            
            # 메시지 수정 
            original_message = await interaction.original_response()
            await original_message.edit(embed=embed, view=self)
            
            print(f">>> 메시지 업데이트 완료: {len(participants_data)}명 참여자")
            
        except Exception as e:
            print(f">>> 메시지 업데이트 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")

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
        
        # 확정 참여자 목록 (4개 역할로 세분화)
        if participants_by_status['confirmed']:
            confirmed_text = self.format_participants_by_detailed_role(participants_by_status['confirmed'])
            embed.add_field(
                name=f"✅ **확정 참여 ({len(participants_by_status['confirmed'])}명)**",
                value=confirmed_text,
                inline=False
            )
        
        # 미정 참여자 목록
        if participants_by_status['tentative']:
            tentative_text = self.format_participants_simple(participants_by_status['tentative'])
            embed.add_field(
                name=f"❓ **미정 ({len(participants_by_status['tentative'])}명)**",
                value=tentative_text,
                inline=False
            )
        
        # 불참자 목록 (간단히)
        if participants_by_status['declined']:
            declined_text = self.format_participants_simple(participants_by_status['declined'])
            embed.add_field(
                name=f"❌ **불참 ({len(participants_by_status['declined'])}명)**",
                value=declined_text,
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

    def format_participants_by_detailed_role(self, participants) -> str:
        """세분화된 역할별로 참여자 포맷팅 (확정 참여자용)"""
        # 역할별 그룹화
        roles = {
            'TANK': [],
            'HEALER': [],
            'MELEE_DPS': [],
            'RANGED_DPS': []
        }
        
        for participant in participants:
            role = participant['detailed_role']
            if role in roles:
                roles[role].append(participant)
            else:
                roles['MELEE_DPS'].append(participant)  # 기본값
        
        result_lines = []
        
        # 탱커
        if roles['TANK']:
            result_lines.append(f"\n🛡️ **탱커 ({len(roles['TANK'])}명)**")
            for p in roles['TANK']:
                class_emoji = get_class_emoji(p['character_class'] or 'unknown')
                spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
                spec_text = f"({spec_kr})" if spec_kr else ""
                result_lines.append(f"   • {class_emoji} {p['character_name']}{spec_text}")
        
        # 힐러
        if roles['HEALER']:
            result_lines.append(f"\n💚 **힐러 ({len(roles['HEALER'])}명)**")
            for p in roles['HEALER']:
                class_emoji = get_class_emoji(p['character_class'] or 'unknown')
                spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
                spec_text = f"({spec_kr})" if spec_kr else ""
                result_lines.append(f"   • {class_emoji} {p['character_name']}{spec_text}")
        
        # 근딜
        if roles['MELEE_DPS']:
            result_lines.append(f"\n⚔️ **근딜 ({len(roles['MELEE_DPS'])}명)**")
            for p in roles['MELEE_DPS']:
                class_emoji = get_class_emoji(p['character_class'] or 'unknown')
                spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
                spec_text = f"({spec_kr})" if spec_kr else ""
                result_lines.append(f"   • {class_emoji} {p['character_name']}{spec_text}")
        
        # 원딜
        if roles['RANGED_DPS']:
            result_lines.append(f"\n🏹 **원딜 ({len(roles['RANGED_DPS'])}명)**")
            for p in roles['RANGED_DPS']:
                class_emoji = get_class_emoji(p['character_class'] or 'unknown')
                spec_kr = translate_spec_en_to_kr(p['character_spec'] or '')
                spec_text = f"({spec_kr})" if spec_kr else ""
                result_lines.append(f"   • {class_emoji} {p['character_name']}{spec_text}")
        
        return '\n'.join(result_lines) if result_lines else "참여자가 없습니다."

    def format_participants_simple(self, participants) -> str:
        """단순한 참여자 목록 (미정/불참용)"""
        result_lines = []
        
        for participant in participants:
            class_emoji = get_class_emoji(participant['character_class'] or 'unknown')
            spec_kr = translate_spec_en_to_kr(participant['character_spec'] or '')
            spec_text = f"({spec_kr})" if spec_kr else ""
            
            line = f"   • {class_emoji} {participant['character_name']}{spec_text}"
            
            # 메모가 있으면 추가
            if participant['participant_notes']:
                line += f" - \"{participant['participant_notes']}\""
            
            result_lines.append(line)
        
        return '\n'.join(result_lines) if result_lines else "해당 없음"

    @staticmethod
    def create_event_embed_static(event_data) -> discord.Embed:
        """정적 임베드 생성 (기본 카운터만)"""
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
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            character_name = self.character_input.value.strip()
            realm_input = self.realm_input.value.strip()
            
            # 사용자 입력을 영어 서버명으로 정규화
            realm_name_en = normalize_realm_input(realm_input)
            realm_name_kr = translate_realm_en_to_kr(realm_name_en)
            
            print(f">>> 캐릭터 변경 시도: {character_name}-{realm_name_en}")
            
            # raider.io API로 캐릭터 유효성 검증
            from utils.character_validator import validate_character, get_character_info
            
            character_valid = await validate_character(realm_name_en, character_name)
            if not character_valid:
                await interaction.followup.send(
                    f"❌ **캐릭터를 찾을 수 없습니다**\n"
                    f"캐릭터: `{character_name}`\n"
                    f"서버: `{realm_input}` → `{realm_name_en}`\n\n"
                    f"정확한 캐릭터명과 서버명을 입력해주세요.",
                    ephemeral=True
                )
                return
            
            # 캐릭터 정보 가져오기
            char_info = await get_character_info(realm_name_en, character_name)
            if not char_info:
                await interaction.followup.send(
                    "❌ 캐릭터 정보를 가져오는데 실패했습니다.",
                    ephemeral=True
                )
                return
            
            # 한국어 번역 적용
            class_kr = translate_class_en_to_kr(char_info.get("class", ""))
            spec_kr = translate_spec_en_to_kr(char_info.get("active_spec_name", ""))
            
            # 세분화된 역할 및 장비 타입 계산
            detailed_role = get_character_role(char_info.get("class"), char_info.get("active_spec_name"))
            armor_type = get_character_armor_type(char_info.get("class"))
            
            # 1. 닉네임 변경 (로켓 이모티콘 추가)
            new_nickname = f"🚀{character_name}"
            try:
                await interaction.user.edit(nick=new_nickname)
                print(f">>> 닉네임 변경 성공: {interaction.user.display_name} -> {new_nickname}")
            except discord.Forbidden:
                print(f">>> 닉네임 변경 실패 (권한 부족): {interaction.user.name}")
            except Exception as e:
                print(f">>> 닉네임 변경 오류: {e}")
            
            # 2. DB에 캐릭터 저장 및 소유권 업데이트
            async with self.db_manager.get_connection() as conn:
                discord_id = str(interaction.user.id)
                
                # 디스코드 사용자 정보 처리
                discord_user_id = await conn.fetchval("""
                    INSERT INTO guild_bot.discord_users (discord_id, discord_username)
                    VALUES ($1, $2)
                    ON CONFLICT (discord_id) DO UPDATE SET
                        discord_username = EXCLUDED.discord_username,
                        updated_at = NOW()
                    RETURNING id
                """, discord_id, interaction.user.name)
                
                # 캐릭터 정보 저장/업데이트
                character_id = await conn.fetchval("""
                    INSERT INTO guild_bot.characters (
                        character_name, realm_slug, race, class, active_spec, 
                        active_spec_role, gender, faction, achievement_points,
                        profile_url, thumbnail_url, region, last_crawled_at,
                        is_guild_member
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
                
                # 기존 verified 캐릭터들을 모두 FALSE로 변경
                await conn.execute("""
                    UPDATE guild_bot.character_ownership 
                    SET is_verified = FALSE, updated_at = NOW()
                    WHERE discord_user_id = $1 AND is_verified = TRUE
                """, discord_user_id)
                
                # 캐릭터 소유권 설정 (새로운 캐릭터를 verified=TRUE로)
                await conn.execute("""
                    INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (discord_user_id, character_id) DO UPDATE SET
                        is_verified = TRUE,
                        updated_at = NOW()
                """, discord_user_id, character_id)
                
                # 3. 기존 참가 정보 확인
                existing = await conn.fetchrow("""
                    SELECT participation_status, character_name, character_class, character_spec, detailed_role
                    FROM guild_bot.event_participations
                    WHERE event_instance_id = $1 AND discord_user_id = $2
                """, self.event_instance_id, discord_user_id)
                
                old_status = existing['participation_status'] if existing else None
                old_character_name = existing['character_name'] if existing else None
                old_character_class = existing['character_class'] if existing else None
                old_character_spec = existing['character_spec'] if existing else None
                old_detailed_role = existing['detailed_role'] if existing else None
                
                # 4. 일정에 자동 참가 (confirmed 상태로 업데이트/삽입)
                if existing:
                    await conn.execute("""
                        UPDATE guild_bot.event_participations
                        SET participation_status = 'confirmed', character_role = $1, detailed_role = $2,
                            character_id = $3, character_name = $4, character_realm = $5,
                            character_class = $6, character_spec = $7, armor_type = $8,
                            participant_notes = NULL, discord_message_id = $9, 
                            discord_channel_id = $10, updated_at = NOW()
                        WHERE event_instance_id = $11 AND discord_user_id = $12
                    """, char_info.get('active_spec_role'), detailed_role, character_id, 
                        char_info.get('name'), char_info.get('realm'), char_info.get('class'),
                        char_info.get('active_spec_name'), armor_type, self.discord_message_id, 
                        self.discord_channel_id, self.event_instance_id, discord_user_id)
                else:
                    await conn.execute("""
                        INSERT INTO guild_bot.event_participations
                        (event_instance_id, character_id, discord_user_id, participation_status, 
                         character_role, detailed_role, character_name, character_realm,
                         character_class, character_spec, armor_type, discord_message_id, discord_channel_id)
                        VALUES ($1, $2, $3, 'confirmed', $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """, self.event_instance_id, character_id, discord_user_id, 
                        char_info.get('active_spec_role'), detailed_role, char_info.get('name'),
                        char_info.get('realm'), char_info.get('class'), char_info.get('active_spec_name'),
                        armor_type, self.discord_message_id, self.discord_channel_id)
                
                # 5. 카운터 업데이트
                signup_view = EventSignupView(self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
                
                # 6. 확장된 로그 기록
                action_type = "character_changed_and_joined" if not old_status else f"character_changed_from_{old_status}"
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, old_status, new_status,
                     character_name, character_realm, character_class, character_spec, detailed_role,
                     old_character_name, old_character_realm, old_character_class, old_character_spec, old_detailed_role,
                     discord_message_id, discord_channel_id, user_display_name)
                    VALUES ($1, $2, $3, $4, $5, 'confirmed', $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                """, self.event_instance_id, character_id, discord_user_id, action_type, old_status,
                    char_info.get('name'), char_info.get('realm'), char_info.get('class'), 
                    char_info.get('active_spec_name'), detailed_role, old_character_name, 
                    char_info.get('realm'), old_character_class, old_character_spec, old_detailed_role,
                    self.discord_message_id, self.discord_channel_id, interaction.user.display_name)
                
                # 7. 성공 메시지
                role_kr = get_role_korean(detailed_role)
                await interaction.followup.send(
                    f"✅ **캐릭터 변경 및 참가 완료!**\n"
                    f"캐릭터: {char_info.get('name')}\n"
                    f"서버: {realm_name_kr}\n"
                    f"직업: {class_kr} ({spec_kr})\n"
                    f"역할: {role_kr}\n"
                    f"닉네임: {new_nickname}\n\n"
                    f"**확정 참여**로 자동 등록되었습니다!",
                    ephemeral=True
                )
                
                # 8. 메시지 업데이트
                signup_view = EventSignupView(self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
                await signup_view.update_event_message(interaction)
                
                print(f">>> 캐릭터 변경 및 참가 완료: {char_info.get('name')}-{char_info.get('realm')}")
                
        except Exception as e:
            print(f">>> 캐릭터 변경 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")
            await interaction.followup.send(
                "❌ 캐릭터 변경 중 오류가 발생했습니다.",
                ephemeral=True
            )


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
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            discord_id = str(interaction.user.id)
            memo = self.memo_input.value.strip() if self.memo_input.value else None
            
            # 닉네임에서 캐릭터명 추출
            nickname = interaction.user.display_name
            clean_name = nickname.replace("🚀", "").replace("⭐", "").strip()
            
            print(f">>> {self.status} 신청 시작: {clean_name}")
            
            # 기존 auto_nickname_handler의 로직 사용
            from cogs.core.auto_nickname import AutoNicknameHandler
            
            handler = AutoNicknameHandler(None)  # bot은 None으로 전달
            handler.db_manager = self.db_manager  # 같은 DB 매니저 사용
            
            # 캐릭터 유효성 체크
            char_result = await handler.check_character_validity(clean_name)
            
            if not char_result:
                await interaction.followup.send(
                    f"❌ **캐릭터를 찾을 수 없습니다**\n"
                    f"현재 닉네임: `{clean_name}`\n\n"
                    f"**🔄 캐릭터변경** 버튼을 눌러주세요.",
                    ephemeral=True
                )
                return
            
            # 모호한 캐릭터인 경우
            if char_result.get("needs_clarification"):
                await interaction.followup.send(
                    f"❌ **모호한 캐릭터명입니다**\n"
                    f"'{clean_name}' 캐릭터가 여러 서버에 존재합니다.\n"
                    f"**🔄 캐릭터변경** 버튼을 눌러서 서버를 명시해주세요.",
                    ephemeral=True
                )
                return
            
            # 캐릭터 정보 처리
            if char_result["source"] == "db":
                # DB에 이미 있는 캐릭터
                character_id = char_result["character_id"]
                character_name = char_result["character_name"]
                realm_slug = char_result["realm_slug"]
                
                # 캐릭터 정보 조회
                async with self.db_manager.get_connection() as conn:
                    char_info_db = await conn.fetchrow("""
                        SELECT character_name, realm_slug, active_spec_role, active_spec, class
                        FROM guild_bot.characters 
                        WHERE id = $1
                    """, character_id)
                    
                    character_role = char_info_db['active_spec_role'] if char_info_db else None
                    character_spec = char_info_db['active_spec'] if char_info_db else None
                    character_class = char_info_db['class'] if char_info_db else None
                    
            else:
                # API에서 가져온 캐릭터
                char_info = char_result["character_info"]
                character_name = char_info.get("name")
                realm_slug = char_result["realm_slug"]
                character_role = char_info.get("active_spec_role")
                character_spec = char_info.get("active_spec_name")
                character_class = char_info.get("class")
                
                # 캐릭터를 DB에 저장
                async with self.db_manager.get_connection() as conn:
                    character_id = await conn.fetchval("""
                        INSERT INTO guild_bot.characters (
                            character_name, realm_slug, race, class, active_spec, 
                            active_spec_role, gender, faction, achievement_points,
                            profile_url, thumbnail_url, region, last_crawled_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())
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
            
            # 세분화된 역할 및 장비 타입 계산
            detailed_role = get_character_role(character_class, character_spec)
            armor_type = get_character_armor_type(character_class)
            
            # 캐릭터 등록 및 참가 처리
            async with self.db_manager.get_connection() as conn:
                # 캐릭터 및 사용자 정보 처리
                discord_user_id = await conn.fetchval("""
                    INSERT INTO guild_bot.discord_users (discord_id, discord_username)
                    VALUES ($1, $2)
                    ON CONFLICT (discord_id) DO UPDATE SET
                        discord_username = EXCLUDED.discord_username,
                        updated_at = NOW()
                    RETURNING id
                """, discord_id, interaction.user.name)
                
                # 캐릭터 소유권 설정
                await conn.execute("""
                    UPDATE guild_bot.character_ownership 
                    SET is_verified = FALSE, updated_at = NOW()
                    WHERE discord_user_id = $1 AND is_verified = TRUE
                """, discord_user_id)
                
                await conn.execute("""
                    INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (discord_user_id, character_id) DO UPDATE SET
                        is_verified = TRUE,
                        updated_at = NOW()
                """, discord_user_id, character_id)
                
                # 기존 참가 정보 확인
                existing = await conn.fetchrow("""
                    SELECT participation_status, character_name, character_class, character_spec, detailed_role
                    FROM guild_bot.event_participations
                    WHERE event_instance_id = $1 AND discord_user_id = $2
                """, self.event_instance_id, discord_user_id)
                
                old_status = existing['participation_status'] if existing else None
                old_character_name = existing['character_name'] if existing else None
                old_character_class = existing['character_class'] if existing else None
                old_character_spec = existing['character_spec'] if existing else None
                old_detailed_role = existing['detailed_role'] if existing else None
                
                # 참가 정보 업데이트/삽입 (메모 포함, 새로운 구조)
                if existing:
                    await conn.execute("""
                        UPDATE guild_bot.event_participations
                        SET participation_status = $1, character_role = $2, detailed_role = $3,
                            character_id = $4, character_name = $5, character_realm = $6,
                            character_class = $7, character_spec = $8, armor_type = $9,
                            participant_notes = $10, discord_message_id = $11, 
                            discord_channel_id = $12, updated_at = NOW()
                        WHERE event_instance_id = $13 AND discord_user_id = $14
                    """, self.status, character_role, detailed_role, character_id, 
                        character_name, realm_slug, character_class, character_spec, 
                        armor_type, memo, self.discord_message_id, self.discord_channel_id,
                        self.event_instance_id, discord_user_id)
                else:
                    await conn.execute("""
                        INSERT INTO guild_bot.event_participations
                        (event_instance_id, character_id, discord_user_id, participation_status, 
                         character_role, detailed_role, character_name, character_realm,
                         character_class, character_spec, armor_type, participant_notes,
                         discord_message_id, discord_channel_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """, self.event_instance_id, character_id, discord_user_id, self.status, 
                        character_role, detailed_role, character_name, realm_slug,
                        character_class, character_spec, armor_type, memo,
                        self.discord_message_id, self.discord_channel_id)
                
                # 카운터 업데이트
                signup_view = EventSignupView(self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
                await signup_view.update_participation_counts(conn, old_status, self.status)
                
                # 확장된 로그 기록
                action_type = "joined" if not old_status else f"changed_to_{self.status}"
                await conn.execute("""
                    INSERT INTO guild_bot.event_participation_logs
                    (event_instance_id, character_id, discord_user_id, action_type, old_status, new_status,
                     character_name, character_realm, character_class, character_spec, detailed_role,
                     old_character_name, old_character_realm, old_character_class, old_character_spec, old_detailed_role,
                     discord_message_id, discord_channel_id, user_display_name, participant_memo)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                """, self.event_instance_id, character_id, discord_user_id, action_type, old_status, self.status,
                    character_name, realm_slug, character_class, character_spec, detailed_role,
                    old_character_name, realm_slug, old_character_class, old_character_spec, old_detailed_role,
                    self.discord_message_id, self.discord_channel_id, interaction.user.display_name, memo)
                
                # 성공 메시지
                status_emoji = {"tentative": "❓", "declined": "❌"}
                status_text = {"tentative": "미정", "declined": "불참"}
                
                memo_text = f"\n사유: {memo}" if memo else ""
                spec_kr = translate_spec_en_to_kr(character_spec or '')
                role_kr = get_role_korean(detailed_role)
                
                await interaction.followup.send(
                    f"{status_emoji[self.status]} **{status_text[self.status]}** 처리 완료!\n"
                    f"캐릭터: {character_name} ({spec_kr})\n"
                    f"역할: {role_kr}"
                    f"{memo_text}",
                    ephemeral=True
                )
                
                # 메시지 업데이트 (중요!)
                signup_view = EventSignupView(self.event_instance_id, self.db_manager, self.discord_message_id, self.discord_channel_id)
                await signup_view.update_event_message(interaction)
                
                print(f">>> {status_text[self.status]} 신청: {character_name} -> {self.status}, 메모: {memo}")
                
        except Exception as e:
            print(f">>> {self.status} 처리 오류: {e}")
            import traceback
            print(f">>> 스택 추적: {traceback.format_exc()}")
            await interaction.followup.send(f"❌ {self.status} 처리 중 오류가 발생했습니다.", ephemeral=True)