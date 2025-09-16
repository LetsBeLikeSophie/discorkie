# services/participation_service.py
from utils.wow_role_mapping import get_character_role, get_character_armor_type


class ParticipationService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def ensure_discord_user(self, discord_id: str, username: str, conn):
        """디스코드 사용자 정보 확인/생성"""
        return await conn.fetchval("""
            INSERT INTO guild_bot.discord_users (discord_id, discord_username)
            VALUES ($1, $2)
            ON CONFLICT (discord_id) DO UPDATE SET
                discord_username = EXCLUDED.discord_username,
                updated_at = NOW()
            RETURNING id
        """, discord_id, username)

    async def get_existing_participation(self, event_instance_id: int, discord_user_id: int, conn):
        """기존 참가 정보 조회"""
        return await conn.fetchrow("""
            SELECT participation_status, character_name, character_class, character_spec, detailed_role
            FROM guild_bot.event_participations
            WHERE event_instance_id = $1 AND discord_user_id = $2
        """, event_instance_id, discord_user_id)

    async def upsert_participation(self, event_instance_id: int, discord_user_id: int, 
                                 character_data: dict, status: str, memo: str,
                                 discord_message_id: int, discord_channel_id: int, conn):
        """참가 정보 업데이트/삽입"""
        detailed_role = get_character_role(character_data['character_class'], character_data['character_spec'])
        armor_type = get_character_armor_type(character_data['character_class'])
        
        # 기존 참가 정보 확인
        existing = await self.get_existing_participation(event_instance_id, discord_user_id, conn)
        
        if existing:
            await conn.execute("""
                UPDATE guild_bot.event_participations
                SET participation_status = $1, character_role = $2, detailed_role = $3,
                    character_id = $4, character_name = $5, character_realm = $6,
                    character_class = $7, character_spec = $8, armor_type = $9,
                    participant_notes = $10, discord_message_id = $11, 
                    discord_channel_id = $12, updated_at = NOW()
                WHERE event_instance_id = $13 AND discord_user_id = $14
            """, status, character_data['character_role'], detailed_role, 
                character_data['character_id'], character_data['character_name'], 
                character_data['realm_slug'], character_data['character_class'], 
                character_data['character_spec'], armor_type, memo,
                discord_message_id, discord_channel_id, event_instance_id, discord_user_id)
        else:
            await conn.execute("""
                INSERT INTO guild_bot.event_participations
                (event_instance_id, character_id, discord_user_id, participation_status, 
                 character_role, detailed_role, character_name, character_realm,
                 character_class, character_spec, armor_type, participant_notes,
                 discord_message_id, discord_channel_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """, event_instance_id, character_data['character_id'], discord_user_id, status, 
                character_data['character_role'], detailed_role, character_data['character_name'], 
                character_data['realm_slug'], character_data['character_class'], 
                character_data['character_spec'], armor_type, memo,
                discord_message_id, discord_channel_id)
        
        return existing, detailed_role

    async def log_participation_action(self, event_instance_id: int, character_data: dict, 
                                 discord_user_id: int, old_participation, new_status: str,
                                 detailed_role: str, discord_message_id: int, 
                                 discord_channel_id: int, user_display_name: str, 
                                 memo: str, conn):
        """참가 로그 기록"""
        old_status = old_participation['participation_status'] if old_participation else None
        old_character_name = old_participation['character_name'] if old_participation else None
        old_detailed_role = old_participation['detailed_role'] if old_participation else None
        
        action_type = "joined" if not old_status else f"changed_to_{new_status}"
        
        await conn.execute("""
            INSERT INTO guild_bot.event_participation_logs
            (event_instance_id, character_id, discord_user_id, action_type, old_status, new_status,
            character_name, character_realm, character_class, character_spec, detailed_role,
            old_character_name, old_detailed_role,
            discord_message_id, discord_channel_id, user_display_name, participant_memo)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
        """, event_instance_id, character_data['character_id'], discord_user_id, action_type, 
            old_status, new_status, character_data['character_name'], character_data['realm_slug'], 
            character_data['character_class'], character_data['character_spec'], detailed_role,
            old_character_name, old_detailed_role, discord_message_id, discord_channel_id, 
            user_display_name, memo)