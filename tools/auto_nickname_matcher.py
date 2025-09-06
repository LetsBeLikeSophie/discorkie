#!/usr/bin/env python3
"""
auto_nickname_matcher.py

기존 디스코드 서버 멤버들의 닉네임을 characters 테이블과 매칭하여
자동으로 이모지 추가 + character_ownership 연결을 수행하는 스크립트

개선사항:
- 유일한 서버에서만 발견된 캐릭터 → 🚀 로켓 이모티콘
- 여러 서버에 같은 이름이 있는 캐릭터 → ❓ 물음표 이모티콘
- 길드원이 아닌 캐릭터도 DB에 추가
- 상세한 로그 출력
- 2개 이상 발견 시 조기 중단으로 성능 최적화
"""
import discord
import asyncio
import os
import sys
from typing import Dict, List, Tuple, Optional
import aiohttp

# sys.path 설정을 먼저 해야 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 그 다음에 db 모듈 import
from db.database_manager import DatabaseManager
from utils.character_validator import validate_character, get_character_info

# 설정값
GUILD_ID = 1275099769731022971  # 서버 ID
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

class AutoNicknameMatcher:
    def __init__(self):
        self.bot = None
        self.guild = None
        self.db_manager = DatabaseManager()
        
    async def connect_to_discord(self):
        """디스코드 봇 연결 (타임아웃 적용)"""
        intents = discord.Intents.default()
        intents.members = True
        
        self.bot = discord.Client(intents=intents)
        
        # 연결 완료 이벤트를 기다리기 위한 Future
        ready_future = asyncio.Future()
        
        @self.bot.event
        async def on_ready():
            print(f">>> 봇 로그인 완료: {self.bot.user}")
            self.guild = self.bot.get_guild(GUILD_ID)
            if self.guild:
                print(f">>> 길드 연결 완료: {self.guild.name} (멤버수: {self.guild.member_count})")
                ready_future.set_result(True)
            else:
                print(f">>> 길드를 찾을 수 없음: {GUILD_ID}")
                ready_future.set_exception(Exception(f"길드를 찾을 수 없음: {GUILD_ID}"))
        
        # 봇 시작
        bot_task = asyncio.create_task(self.bot.start(BOT_TOKEN))
        
        try:
            # 30초 타임아웃으로 ready 이벤트 대기
            await asyncio.wait_for(ready_future, timeout=30.0)
            print(">>> 디스코드 연결 및 준비 완료")
        except asyncio.TimeoutError:
            print(">>> 디스코드 연결 타임아웃 (30초)")
            bot_task.cancel()
            raise
        except Exception as e:
            print(f">>> 디스코드 연결 오류: {e}")
            bot_task.cancel()
            raise
    
    async def get_characters_from_db(self) -> Dict[str, List[Tuple[str, int, bool]]]:
        """DB에서 모든 캐릭터 목록 가져오기 (길드원 여부 포함)"""
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT character_name, realm_slug, id, is_guild_member
                    FROM guild_bot.characters 
                """)
            
            # 캐릭터명 -> (realm_slug, character_id, is_guild_member) 매핑
            characters = {}
            for row in rows:
                char_name = row['character_name']
                realm_slug = row['realm_slug']
                char_id = row['id']
                is_guild_member = row['is_guild_member']
                
                if char_name not in characters:
                    characters[char_name] = []
                characters[char_name].append((realm_slug, char_id, is_guild_member))
            
            print(f">>> DB에서 {len(characters)}개 캐릭터명 발견")
            return characters
            
        except Exception as e:
            print(f">>> DB 조회 오류: {e}")
            return {}
    
    async def check_character_validity(self, character_name: str, db_characters: Dict) -> Optional[Dict]:
        """캐릭터 유효성 검사 및 서버 확인"""
        
        print(f">>> 캐릭터 유효성 검사 시작: {character_name}")
        
        # 1. DB에서 캐릭터 확인 (길드원/비길드원 무관)
        if character_name in db_characters:
            char_list = db_characters[character_name]
            print(f">>> DB에서 발견: {character_name} - {len(char_list)}개 서버")
            
            for i, (realm, char_id, is_guild) in enumerate(char_list):
                guild_status = "길드원" if is_guild else "비길드원"
                print(f">>>   [{i+1}] {character_name}-{realm} (ID: {char_id}, {guild_status})")
            
            if len(char_list) == 1:
                # 유일한 캐릭터 발견
                realm_slug, character_id, is_guild_member = char_list[0]
                guild_status = "길드원" if is_guild_member else "비길드원"
                print(f">>> DB에서 유일한 캐릭터 발견: {character_name}-{realm_slug} ({guild_status})")
                return {
                    "source": "db",
                    "character_name": character_name,
                    "realm_slug": realm_slug,
                    "character_id": character_id,
                    "is_guild_member": is_guild_member
                }
            else:
                # 여러 서버에 같은 이름 존재
                print(">>> 여러 서버에 같은 캐릭터명 존재, 물음표 처리")
                return {
                    "source": "db_ambiguous",
                    "character_name": character_name,
                    "servers": [realm for realm, _, _ in char_list],
                    "needs_clarification": True
                }
        
        # 2. DB에 없으면 API로 검사
        print(f">>> DB에 없음, API로 검사: {character_name}")
        
        # 주요 서버들 (우선순위 순 - 길드 서버 우선)
        servers_to_check = [
            "Hyjal", "Azshara", "Gul'dan", "Deathwing", "Burning Legion",
            "Stormrage", "Windrunner", "Zul'jin", "Dalaran", "Durotan"
        ]
        
        found_servers = []
        
        for server in servers_to_check:
            try:
                print(f">>> API 서버 검사: {character_name}-{server}")
                if await validate_character(server, character_name):
                    print(f">>> API에서 발견: {character_name}-{server}")
                    char_info = await get_character_info(server, character_name)
                    if char_info:
                        found_servers.append((server, char_info))
                        
                        # 2개 이상 발견되면 바로 중단 (어차피 모호함 처리)
                        if len(found_servers) >= 2:
                            print(f">>> 2개 이상 서버에서 발견, 검사 중단: {character_name}")
                            break
                            
                # API 호출 제한을 위한 대기
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f">>> API 검사 오류 ({server}): {e}")
                continue
        
        # API 검사 결과 분석
        if len(found_servers) == 0:
            print(f">>> 어떤 서버에서도 찾을 수 없음: {character_name}")
            return None
        elif len(found_servers) == 1:
            # 유일한 서버에서 발견
            server, char_info = found_servers[0]
            print(f">>> API에서 유일한 서버에 발견: {character_name}-{server}")
            return {
                "source": "api",
                "character_info": char_info,
                "realm_slug": server,
                "is_guild_member": False  # API로 찾은 것은 일단 비길드원으로 간주
            }
        else:
            # 여러 서버에서 발견
            print(f">>> API에서 여러 서버에 발견: {character_name} ({len(found_servers)}개 서버)")
            for i, (server, _) in enumerate(found_servers):
                print(f">>>   [{i+1}] {character_name}-{server}")
            print(">>> 모호한 API 캐릭터로 물음표 처리")
            return {
                "source": "api_ambiguous",
                "character_name": character_name,
                "servers": [server for server, _ in found_servers],
                "needs_clarification": True
            }

    async def save_character_to_db(self, char_info: dict, is_guild_member: bool = False) -> bool:
        """캐릭터 정보를 DB에 저장"""
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

            print(f">>> characters 테이블 저장 시도: {name}-{realm} (길드원: {is_guild_member})")
            
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

    async def link_character_to_discord_user(self, character_id: int, member: discord.Member) -> bool:
        """캐릭터를 디스코드 유저에게 연결"""
        try:
            async with self.db_manager.get_connection() as conn:
                discord_id = str(member.id)
                discord_username = member.name
                
                print(f">>> 디스코드 연결 시작: 캐릭터ID {character_id} -> {discord_username}#{discord_id}")
                
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
                
                # 3. 기존 verified 연결 해제 (한 유저당 하나의 활성 캐릭터만)
                await conn.execute("""
                    UPDATE guild_bot.character_ownership 
                    SET is_verified = FALSE, updated_at = NOW()
                    WHERE discord_user_id = $1 AND is_verified = TRUE
                """, discord_user_db_id)
                
                # 4. 새로운 연결 추가/업데이트
                await conn.execute("""
                    INSERT INTO guild_bot.character_ownership (discord_user_id, character_id, is_verified)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (discord_user_id, character_id)
                    DO UPDATE SET
                        is_verified = TRUE,
                        updated_at = NOW()
                """, discord_user_db_id, character_id)
            
            print(f">>> 디스코드 연결 성공: 캐릭터ID {character_id} -> {discord_username}")
            return True
            
        except Exception as e:
            print(f">>> DB 연결 오류 ({member.display_name}): {e}")
            return False

    async def get_character_id_from_db(self, character_name: str, realm_slug: str) -> Optional[int]:
        """DB에서 캐릭터 ID 조회"""
        try:
            async with self.db_manager.get_connection() as conn:
                character_id = await conn.fetchval(
                    "SELECT id FROM guild_bot.characters WHERE character_name = $1 AND realm_slug = $2",
                    character_name, realm_slug
                )
                
                if character_id:
                    print(f">>> 캐릭터 ID 조회 성공: {character_name}-{realm_slug} -> ID {character_id}")
                else:
                    print(f">>> 캐릭터 ID 조회 실패: {character_name}-{realm_slug}")
                
                return character_id
                
        except Exception as e:
            print(f">>> 캐릭터 ID 조회 오류: {e}")
            return None
    
    async def process_members(self):
        """모든 멤버 처리"""
        if not self.guild:
            print(">>> 길드가 연결되지 않음")
            return
        
        # DB에서 캐릭터 목록 가져오기
        characters = await self.get_characters_from_db()
        if not characters:
            print(">>> 처리할 캐릭터가 없음")
            return
        
        processed_count = 0
        success_count = 0
        skip_count = 0
        error_count = 0
        no_match_count = 0
        ambiguous_count = 0
        question_mark_count = 0
        
        print(">>> 멤버 처리 시작...")
        
        # fetch_members 대신 guild.members 사용 (이미 캐시된 멤버들)
        members = self.guild.members
        print(f">>> 처리할 멤버 수: {len(members)}")
        
        for member in members:
            # 봇 건너뛰기
            if member.bot:
                continue
            
            processed_count += 1
            current_nickname = member.display_name
            
            # 진행 상황 출력 (50명마다)
            if processed_count % 50 == 0:
                print(f">>> 처리 진행: {processed_count}명 완료...")
            
            # 이미 로켓/물음표 이모지가 있으면 건너뛰기
            if current_nickname.startswith("🚀") or current_nickname.startswith("❓"):
                print(f">>> 이미 처리됨 건너뛰기: {current_nickname}")
                skip_count += 1
                continue
            
            # 로켓/물음표 이모지 제거해서 캐릭터명 추출
            character_name = current_nickname.replace("🚀", "").replace("❓", "").strip()
            print(f">>> 처리 중: {member.name} -> 캐릭터명 '{character_name}'")
            
            # 캐릭터 유효성 검사
            char_result = await self.check_character_validity(character_name, characters)
            
            if char_result:
                print(f">>> 유효한 캐릭터 발견: {character_name} (소스: {char_result['source']})")
                
                # 모호한 경우와 확실한 경우 구분
                if char_result.get("needs_clarification"):
                    # 여러 서버에 존재하는 모호한 캐릭터 - 물음표 추가
                    new_nickname = f"❓{character_name}"
                    
                    # 닉네임 변경 시도
                    try:
                        await member.edit(nick=new_nickname)
                        print(f">>> 물음표 추가 성공 (모호한 캐릭터): {member.name} -> {new_nickname}")
                        servers_list = ", ".join(char_result["servers"])
                        print(f">>> 존재하는 서버들: {servers_list}")
                        question_mark_count += 1
                    except discord.Forbidden:
                        print(f">>> 물음표 추가 실패 (권한 부족): {member.name}")
                        error_count += 1
                        continue
                    except Exception as e:
                        print(f">>> 물음표 추가 오류 ({member.name}): {e}")
                        error_count += 1
                        continue
                        
                else:
                    # 유일한 서버에서 확인된 캐릭터 - 로켓 추가
                    new_nickname = f"🚀{character_name}"
                    
                    # 닉네임 변경 시도
                    nickname_changed = False
                    try:
                        await member.edit(nick=new_nickname)
                        nickname_changed = True
                        print(f">>> 로켓 추가 성공 (확실한 캐릭터): {member.name} -> {new_nickname}")
                    except discord.Forbidden:
                        print(f">>> 로켓 추가 실패 (권한 부족): {member.name}")
                        error_count += 1
                        continue
                    except Exception as e:
                        print(f">>> 로켓 추가 오류 ({member.name}): {e}")
                        error_count += 1
                        continue
                    
                    # 닉네임 변경 성공 시 DB 처리
                    if nickname_changed:
                        character_id = None
                        
                        if char_result["source"] == "db":
                            # DB에 이미 있는 캐릭터
                            character_id = char_result["character_id"]
                            print(f">>> DB 캐릭터 사용: ID {character_id}")
                            
                        elif char_result["source"] == "api":
                            # API에서 찾은 캐릭터 - DB에 저장 필요
                            char_info = char_result["character_info"]
                            save_success = await self.save_character_to_db(char_info, is_guild_member=False)
                            
                            if save_success:
                                # 저장된 캐릭터의 ID 조회
                                character_id = await self.get_character_id_from_db(
                                    character_name, char_result["realm_slug"]
                                )
                                print(f">>> API 캐릭터 저장 완료: ID {character_id}")
                            else:
                                print(f">>> API 캐릭터 저장 실패: {character_name}")
                                error_count += 1
                                continue
                        
                        # 디스코드 연결
                        if character_id:
                            db_success = await self.link_character_to_discord_user(character_id, member)
                            if db_success:
                                print(f">>> 전체 처리 성공: {new_nickname} <-> 캐릭터ID {character_id}")
                                success_count += 1
                            else:
                                print(f">>> DB 연결 실패: {new_nickname}")
                                error_count += 1
                        else:
                            print(f">>> 캐릭터 ID 없음: {character_name}")
                            error_count += 1
                
                # API 호출 제한을 위한 잠시 대기
                await asyncio.sleep(0.5)
            
            else:
                # 매칭 없거나 무효한 경우
                if character_name in characters and len(characters[character_name]) > 1:
                    ambiguous_count += 1
                    if ambiguous_count <= 5:  # 처음 5개만 출력
                        print(f">>> 모호한 매칭: {character_name}")
                else:
                    no_match_count += 1
                    if no_match_count <= 10:  # 처음 10개만 출력
                        print(f">>> 매칭 없음: {character_name}")
                    elif no_match_count == 11:
                        print(">>> 매칭 없는 멤버가 많아 로그 생략...")
        
        print("\n>>> 처리 결과:")
        print(f">>> 총 처리된 멤버: {processed_count}")
        print(f">>> 로켓 추가 성공: {success_count}")
        print(f">>> 물음표 추가 성공: {question_mark_count}")
        print(f">>> 건너뛰기 (이미 처리됨): {skip_count}")
        print(f">>> 오류: {error_count}")
        print(f">>> 매칭 없음: {no_match_count}")
        print(f">>> 모호한 매칭: {ambiguous_count}")
    
    async def run(self):
        """메인 실행 함수"""
        try:
            print(">>> 자동 닉네임 매칭 시작")
            
            # 데이터베이스 연결 풀 생성
            await self.db_manager.create_pool()
            
            # 디스코드 연결 (타임아웃 적용)
            print(">>> 디스코드 연결 시도 중...")
            await self.connect_to_discord()
            
            # 길드 상태 확인
            if not self.guild:
                raise Exception("길드 연결 실패")
                
            print(f">>> 길드 연결 확인 완료: {self.guild.name}")
            print(f">>> 초기 캐시된 멤버 수: {len(self.guild.members)}")
            
            # 길드 멤버 캐시 완료까지 대기 (간소화)
            print(">>> 멤버 정보 로딩 완료 대기...")
            
            # 간단한 대기 방식으로 변경
            await asyncio.sleep(10)  # 10초 대기
            
            final_cached = len(self.guild.members)
            print(f">>> 최종 캐시된 멤버 수: {final_cached}")
            
            if final_cached == 0:
                print(">>> 경고: 캐시된 멤버가 없음. 권한 문제일 수 있음")
                print(">>> fetch_members()로 강제 조회 시도...")
            
            # 멤버 처리
            await self.process_members()
            
        except Exception as e:
            print(f">>> 실행 오류: {e}")
        finally:
            # 정리 작업
            if self.bot and not self.bot.is_closed():
                await self.bot.close()
                print(">>> 디스코드 연결 종료")
            await self.db_manager.close_pool()
            print(">>> 작업 완료")

async def main():
    """메인 함수"""
    if not BOT_TOKEN:
        print(">>> DISCORD_TOKEN 환경변수가 없습니다")
        return
    
    if not os.getenv("DATABASE_URL"):
        print(">>> DATABASE_URL 환경변수가 없습니다")
        return
    
    matcher = AutoNicknameMatcher()
    await matcher.run()

if __name__ == "__main__":
    # Ctrl+C 처리를 위한 신호 핸들러
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n>>> 사용자에 의한 중단")
    except Exception as e:
        print(f">>> 예상치 못한 오류: {e}")