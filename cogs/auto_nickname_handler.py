import discord
from discord.ext import commands
from db.database_manager import DatabaseManager
from utils.character_validator import validate_character, get_character_info
import asyncio
from typing import Optional, Dict, List, Tuple

class AutoNicknameHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.processing_users = set()  # 중복 처리 방지
        
    async def cog_load(self):
        """코그 로드 시 DB 연결"""
        await self.db_manager.create_pool()
        print(">>> AutoNicknameHandler: 데이터베이스 연결 완료")

    async def cog_unload(self):
        """코그 언로드 시 DB 연결 해제"""
        await self.db_manager.close_pool()
        print(">>> AutoNicknameHandler: 데이터베이스 연결 해제")

    async def get_characters_from_db(self, character_name: str) -> List[Tuple[str, int]]:
        """DB에서 캐릭터 정보 조회"""
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT realm_slug, id
                    FROM guild_bot.characters 
                    WHERE character_name = $1 AND is_guild_member = TRUE
                """, character_name)
            
            return [(row['realm_slug'], row['id']) for row in rows]
            
        except Exception as e:
            print(f">>> DB 캐릭터 조회 오류: {e}")
            return []

    async def save_character_to_db(self, char_info: dict, is_guild_member: bool = False) -> bool:
        """캐릭터 정보를 characters 테이블에 저장"""
        try:
            name = char_info.get("name")
            realm = char_info.get("realm")
            
            if not name or not realm:
                print(f">>> 필수 데이터 누락: name={name}, realm={realm}")
                return False
            
            # raider.io API 응답값 그대로 사용
            race = char_info.get("race", "")
            class_name = char_info.get("class", "")
            active_spec = char_info.get("active_spec_name", "")
            active_spec_role = char_info.get("active_spec_role", "")
            gender = char_info.get("gender", "")
            faction = char_info.get("faction", "")

            print(f">>> characters 테이블 저장 시도: {name}-{realm}")
            
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO guild_bot.characters (
                        character_name, realm_slug, is_guild_member,
                        race, class, active_spec, active_spec_role,
                        gender, faction, achievement_points,
                        profile_url, profile_banner, thumbnail_url, region, last_crawled_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7,
                            $8, $9, $10, $11, $12, $13, $14, NOW())
                    ON CONFLICT (character_name, realm_slug)
                    DO UPDATE SET
                        race = EXCLUDED.race,
                        class = EXCLUDED.class,
                        active_spec = EXCLUDED.active_spec,
                        active_spec_role = EXCLUDED.active_spec_role,
                        gender = EXCLUDED.gender,
                        faction = EXCLUDED.faction,
                        achievement_points = EXCLUDED.achievement_points,
                        profile_url = EXCLUDED.profile_url,
                        profile_banner = EXCLUDED.profile_banner,
                        thumbnail_url = EXCLUDED.thumbnail_url,
                        last_crawled_at = NOW(),
                        updated_at = NOW()
                """,
                name, realm, is_guild_member, race, class_name, active_spec, active_spec_role,
                gender, faction, char_info.get("achievement_points", 0),
                char_info.get("profile_url", ""), char_info.get("profile_banner", ""),
                char_info.get("thumbnail_url", ""), "kr"
                )
            
            print(f">>> characters 테이블 저장 성공: {name}-{realm}")
            return True
            
        except Exception as e:
            print(f">>> characters 테이블 저장 오류: {e}")
            return False

    async def link_character_to_discord(self, character_name: str, realm_slug: str, user: discord.Member) -> bool:
        """캐릭터를 디스코드 유저에게 연결"""
        try:
            async with self.db_manager.get_connection() as conn:
                discord_id = str(user.id)
                discord_username = user.name
                
                print(f">>> 디스코드 연결 시작: {character_name}-{realm_slug} -> {discord_username}#{discord_id}")
                
                # 1. discord_users 테이블에 유저 정보 추가/업데이트
                await conn.execute("""
                    INSERT INTO guild_bot.discord_users (discord_id, discord_username)
                    VALUES ($1, $2)
                    ON CONFLICT (discord_id)
                    DO UPDATE SET
                        discord_username = EXCLUDED.discord_username,
                        updated_at = NOW()
                """, discord_id, discord_username)
                
                # 2. discord_user_id 조회
                discord_user_db_id = await conn.fetchval(
                    "SELECT id FROM guild_bot.discord_users WHERE discord_id = $1",
                    discord_id
                )
                
                # 3. character_id 조회
                character_db_id = await conn.fetchval(
                    "SELECT id FROM guild_bot.characters WHERE character_name = $1 AND realm_slug = $2",
                    character_name, realm_slug
                )
                
                if not character_db_id:
                    print(f">>> 캐릭터를 찾을 수 없음: {character_name}-{realm_slug}")
                    return False
                
                # 4. 기존 verified 연결 해제 (한 유저당 하나의 활성 캐릭터만)
                await conn.execute("""
                    UPDATE guild_bot.character_ownership 
                    SET is_verified = FALSE, updated_at = NOW()
                    WHERE discord_user_id = $1 AND is_verified = TRUE
                """, discord_user_db_id)
                
                # 5. 새로운 연결 추가/업데이트
                await conn.execute("""
                    INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (discord_user_id, character_id)
                    DO UPDATE SET
                        is_verified = TRUE,
                        updated_at = NOW()
                """, discord_user_db_id, character_db_id)
                
                print(f">>> 디스코드 연결 성공: {character_name}-{realm_slug} -> {discord_username}#{discord_id}")
                return True
                
        except Exception as e:
            print(f">>> 디스코드 연결 오류: {e}")
            return False

    async def check_character_validity(self, character_name: str) -> Optional[Dict]:
        """캐릭터 유효성 검사 (DB 우선, 없으면 API)"""
        
        # 1. DB에서 길드 캐릭터 확인
        db_characters = await self.get_characters_from_db(character_name)
        if db_characters:
            print(f">>> DB에서 길드 캐릭터 발견: {character_name}")
            realm_slug, character_id = db_characters[0]  # 첫 번째 서버 선택
            return {
                "source": "db",
                "character_name": character_name,
                "realm_slug": realm_slug,
                "character_id": character_id,
                "is_guild_member": True
            }
        
        # 2. API로 유효성 검사 (여러 서버 시도)
        print(f">>> API로 캐릭터 유효성 검사: {character_name}")
        
        # 주요 서버들 (우선순위 순)
        servers_to_check = [
            "Azshara", "Hyjal", "Gul'dan", "Deathwing", "Burning Legion",
            "Stormrage", "Windrunner", "Zul'jin", "Dalaran", "Durotan"
        ]
        
        for server in servers_to_check:
            try:
                if await validate_character(server, character_name):
                    print(f">>> API에서 캐릭터 발견: {character_name}-{server}")
                    char_info = await get_character_info(server, character_name)
                    if char_info:
                        return {
                            "source": "api",
                            "character_info": char_info,
                            "realm_slug": server,
                            "is_guild_member": False
                        }
                # API 호출 제한을 위한 짧은 대기
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f">>> API 검사 오류 ({server}): {e}")
                continue
        
        print(f">>> 유효한 캐릭터를 찾을 수 없음: {character_name}")
        return None

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """멤버 정보 업데이트 시 자동 처리"""
        
        # 닉네임이 변경되지 않았으면 무시
        if before.display_name == after.display_name:
            return
        
        # 특정 길드만 처리
        if after.guild.id != 1275099769731022971:
            return
        
        # 봇은 무시
        if after.bot:
            return
        
        # 중복 처리 방지
        if after.id in self.processing_users:
            return
        
        self.processing_users.add(after.id)
        
        try:
            new_nickname = after.display_name
            print(f">>> 닉네임 변경 감지: {before.display_name} -> {new_nickname}")
            
            # 🚀 이모티콘 제거해서 캐릭터명 추출
            character_name = new_nickname.replace("🚀", "").strip()
            
            # 빈 문자열이거나 너무 짧으면 무시
            if len(character_name) < 2:
                print(f">>> 캐릭터명이 너무 짧음: '{character_name}'")
                return
            
            # 캐릭터 유효성 검사
            char_result = await self.check_character_validity(character_name)
            
            if char_result:
                print(f">>> 유효한 캐릭터 발견: {character_name}")
                
                # 🚀 이모티콘이 없으면 추가
                if not new_nickname.startswith("🚀"):
                    try:
                        new_emoji_nickname = f"🚀{character_name}"
                        await after.edit(nick=new_emoji_nickname)
                        print(f">>> 이모티콘 추가: {new_nickname} -> {new_emoji_nickname}")
                    except discord.Forbidden:
                        print(f">>> 이모티콘 추가 실패 (권한 부족): {after.name}")
                    except Exception as e:
                        print(f">>> 이모티콘 추가 오류: {e}")
                
                # 데이터베이스 업데이트
                if char_result["source"] == "db":
                    # DB에 있는 길드 캐릭터
                    success = await self.link_character_to_discord(
                        character_name, 
                        char_result["realm_slug"], 
                        after
                    )
                    if success:
                        print(f">>> DB 길드 캐릭터 연결 성공: {character_name}")
                    
                elif char_result["source"] == "api":
                    # API에서 찾은 외부 캐릭터
                    char_info = char_result["character_info"]
                    
                    # 캐릭터 정보를 DB에 저장
                    save_success = await self.save_character_to_db(char_info, is_guild_member=False)
                    
                    # 디스코드 연결
                    link_success = await self.link_character_to_discord(
                        character_name,
                        char_result["realm_slug"],
                        after
                    )
                    
                    if save_success and link_success:
                        print(f">>> API 캐릭터 저장 및 연결 성공: {character_name}")
                    else:
                        print(f">>> API 캐릭터 처리 일부 실패: save={save_success}, link={link_success}")
            
            else:
                print(f">>> 유효하지 않은 캐릭터: {character_name}")
                # 🚀 이모티콘이 있으면 제거
                if new_nickname.startswith("🚀"):
                    try:
                        clean_nickname = character_name
                        await after.edit(nick=clean_nickname)
                        print(f">>> 무효한 캐릭터, 이모티콘 제거: {new_nickname} -> {clean_nickname}")
                    except discord.Forbidden:
                        print(f">>> 이모티콘 제거 실패 (권한 부족): {after.name}")
                    except Exception as e:
                        print(f">>> 이모티콘 제거 오류: {e}")
        
        except Exception as e:
            print(f">>> on_member_update 처리 오류: {e}")
        
        finally:
            # 처리 완료 후 사용자 ID 제거
            await asyncio.sleep(1)  # 짧은 대기 후 제거
            self.processing_users.discard(after.id)

async def setup(bot):
    await bot.add_cog(AutoNicknameHandler(bot))