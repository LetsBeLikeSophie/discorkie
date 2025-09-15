# services/character_service.py
from utils.wow_translation import translate_spec_en_to_kr, translate_class_en_to_kr
from utils.wow_role_mapping import get_character_role, get_character_armor_type


class CharacterService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def validate_and_get_character(self, clean_name: str):
        """캐릭터 유효성 검증 및 정보 반환"""
        from cogs.core.auto_nickname import AutoNicknameHandler
        
        handler = AutoNicknameHandler(None)
        handler.db_manager = self.db_manager
        
        char_result = await handler.check_character_validity(clean_name)
        
        if not char_result:
            return {"error": "캐릭터를 찾을 수 없습니다", "needs_clarification": False}
        
        if char_result.get("needs_clarification"):
            return {"error": "모호한 캐릭터명입니다", "needs_clarification": True}
            
        return {"success": True, "char_result": char_result}

    async def save_character_to_db(self, char_result: dict, conn):
        """캐릭터 정보를 DB에 저장하고 ID 반환"""
        if char_result["source"] == "db":
            # DB에 이미 있는 캐릭터
            return {
                "character_id": char_result["character_id"],
                "character_name": char_result["character_name"],
                "realm_slug": char_result["realm_slug"],
                "character_role": None,  # 별도 조회 필요
                "character_spec": None,
                "character_class": None
            }
        
        # API에서 가져온 캐릭터 저장
        char_info = char_result["character_info"]
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
        
        return {
            "character_id": character_id,
            "character_name": char_info.get("name"),
            "realm_slug": char_info.get("realm"),
            "character_role": char_info.get("active_spec_role"),
            "character_spec": char_info.get("active_spec_name"),
            "character_class": char_info.get("class")
        }

    async def get_character_details(self, character_id: int, conn):
        """DB에서 캐릭터 세부 정보 조회"""
        return await conn.fetchrow("""
            SELECT character_name, realm_slug, active_spec_role, active_spec, class
            FROM guild_bot.characters 
            WHERE id = $1
        """, character_id)

    async def set_character_ownership(self, discord_user_id: int, character_id: int, conn):
        """캐릭터 소유권 설정"""
        # 기존 verified 캐릭터들을 FALSE로 변경
        await conn.execute("""
            UPDATE guild_bot.character_ownership 
            SET is_verified = FALSE, updated_at = NOW()
            WHERE discord_user_id = $1 AND is_verified = TRUE
        """, discord_user_id)
        
        # 새 캐릭터를 verified=TRUE로 설정
        await conn.execute("""
            INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
            VALUES ($1, $2, TRUE)
            ON CONFLICT (discord_user_id, character_id) DO UPDATE SET
                is_verified = TRUE,
                updated_at = NOW()
        """, discord_user_id, character_id)

    async def validate_character_from_input(self, character_name: str, realm_input: str):
        """사용자 입력으로부터 캐릭터 검증 (캐릭터변경 모달용)"""
        from utils.wow_translation import normalize_realm_input, translate_realm_en_to_kr
        from utils.character_validator import validate_character, get_character_info
        
        realm_name_en = normalize_realm_input(realm_input)
        realm_name_kr = translate_realm_en_to_kr(realm_name_en)
        
        # API 검증
        character_valid = await validate_character(realm_name_en, character_name)
        if not character_valid:
            return {
                "error": f"캐릭터를 찾을 수 없습니다\n캐릭터: `{character_name}`\n서버: `{realm_input}` → `{realm_name_en}`"
            }
        
        # 캐릭터 정보 가져오기
        char_info = await get_character_info(realm_name_en, character_name)
        if not char_info:
            return {"error": "캐릭터 정보를 가져오는데 실패했습니다."}
        
        return {
            "success": True,
            "char_info": char_info,
            "realm_name_kr": realm_name_kr,
            "realm_name_en": realm_name_en
        }