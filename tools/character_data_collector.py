#!/usr/bin/env python3
"""
auto_nickname_matcher.py

기존 디스코드 서버 멤버들의 닉네임을 characters 테이블과 매칭하여
자동으로 이모지 추가 + character_ownership 연결을 수행하는 스크립트
"""

import discord
import asyncpg
import asyncio
import os
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

# 설정값
GUILD_ID = 1275099769731022971  # 서버 ID
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

class AutoNicknameMatcher:
    def __init__(self):
        self.bot = None
        self.guild = None
        self.pool: Optional[asyncpg.Pool] = None
        
    async def create_pool(self):
        """데이터베이스 연결 풀 생성"""
        try:
            self.pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=10
            )
            print(">>> 데이터베이스 연결 풀 생성 완료")
        except Exception as e:
            print(f">>> 데이터베이스 연결 실패: {e}")
            raise
    
    async def close_pool(self):
        """데이터베이스 연결 풀 종료"""
        if self.pool:
            await self.pool.close()
            print(">>> 데이터베이스 연결 풀 종료")
        
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
    
    async def get_characters_from_db(self) -> Dict[str, List[Tuple[str, int]]]:
        """DB에서 길드 캐릭터 목록 가져오기"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT character_name, realm_slug, id
                    FROM guild_bot.characters 
                    WHERE is_guild_member = TRUE
                """)
            
            # 캐릭터명 -> (realm_slug, character_id) 매핑
            characters = {}
            for row in rows:
                char_name = row['character_name']
                realm_slug = row['realm_slug']
                char_id = row['id']
                
                if char_name not in characters:
                    characters[char_name] = []
                characters[char_name].append((realm_slug, char_id))
            
            print(f">>> DB에서 {len(characters)}개 캐릭터명 발견")
            return characters
            
        except Exception as e:
            print(f">>> DB 조회 오류: {e}")
            return {}
    
    async def link_character_to_discord_user(self, character_id: int, member: discord.Member) -> bool:
        """캐릭터를 디스코드 유저에게 연결"""
        try:
            async with self.pool.acquire() as conn:
                discord_id = str(member.id)
                discord_username = member.name
                
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
            
            return True
            
        except Exception as e:
            print(f">>> DB 연결 오류 ({member.display_name}): {e}")
            return False
    
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
            
            # 이미 🚀 이모지가 있으면 건너뛰기
            if current_nickname.startswith("🚀"):
                print(f">>> 이미 처리됨 건너뛰기: {current_nickname}")
                skip_count += 1
                continue
            
            # DB에서 매칭되는 캐릭터 찾기
            if current_nickname in characters:
                character_options = characters[current_nickname]
                
                # 여러 서버에 같은 이름이 있는 경우 첫 번째 선택
                realm_slug, character_id = character_options[0]
                
                if len(character_options) > 1:
                    print(f">>> 다중 서버 캐릭터: {current_nickname}, 첫 번째 선택: {realm_slug}")
                
                print(f">>> 매칭 발견: {current_nickname} -> {current_nickname}-{realm_slug}")
                
                # 새 닉네임 생성
                new_nickname = f"🚀{current_nickname}"
                
                # 닉네임 변경 시도
                nickname_changed = False
                try:
                    await member.edit(nick=new_nickname)
                    nickname_changed = True
                    print(f">>> 닉네임 변경 성공: {member.name} -> {new_nickname}")
                except discord.Forbidden:
                    print(f">>> 닉네임 변경 실패 (권한 부족): {member.name}")
                    error_count += 1
                    continue
                except Exception as e:
                    print(f">>> 닉네임 변경 오류 ({member.name}): {e}")
                    error_count += 1
                    continue
                
                # 닉네임 변경 성공 시 DB 연결
                if nickname_changed:
                    db_success = await self.link_character_to_discord_user(character_id, member)
                    if db_success:
                        print(f">>> DB 연결 성공: {new_nickname} <-> {current_nickname}-{realm_slug}")
                        success_count += 1
                    else:
                        print(f">>> DB 연결 실패: {new_nickname}")
                        error_count += 1
                
                # API 호출 제한을 위한 잠시 대기
                await asyncio.sleep(0.5)
            
            else:
                # 매칭 없는 경우는 로그 레벨 낮춤 (너무 많아서)
                no_match_count += 1
                if no_match_count <= 10:  # 처음 10개만 출력
                    print(f">>> 매칭 없음: {current_nickname}")
                elif no_match_count == 11:
                    print(">>> 매칭 없는 멤버가 많아 로그 생략...")
        
        print("\n>>> 처리 결과:")
        print(f">>> 총 처리된 멤버: {processed_count}")
        print(f">>> 성공: {success_count}")
        print(f">>> 건너뛰기 (이미 처리됨): {skip_count}")
        print(f">>> 오류: {error_count}")
        print(f">>> 매칭 없음: {no_match_count}")
    
    async def run(self):
        """메인 실행 함수"""
        try:
            print(">>> 자동 닉네임 매칭 시작")
            
            # 데이터베이스 연결 풀 생성
            await self.create_pool()
            
            # 디스코드 연결 (타임아웃 적용)
            await self.connect_to_discord()
            
            # 길드 멤버 캐시 완료까지 대기
            print(">>> 멤버 정보 확인 중...")
            
            # 최대 30초까지 멤버 캐시 완료 대기
            for i in range(30):
                cached_count = len(self.guild.members) if self.guild else 0
                total_count = self.guild.member_count if self.guild else 0
                
                print(f">>> 멤버 캐시 진행: {cached_count}/{total_count}")
                
                # 충분한 멤버가 캐시되었거나 완료되었으면 진행
                if cached_count >= total_count * 0.9:  # 90% 이상 캐시되면 진행
                    print(f">>> 멤버 캐시 완료 ({cached_count}/{total_count})")
                    break
                
                await asyncio.sleep(1)
            else:
                print(f">>> 멤버 캐시 타임아웃, 현재 상태로 진행 ({cached_count}/{total_count})")
            
            # 멤버 처리
            await self.process_members()
            
        except Exception as e:
            print(f">>> 실행 오류: {e}")
        finally:
            # 정리 작업
            if self.bot and not self.bot.is_closed():
                await self.bot.close()
                print(">>> 디스코드 연결 종료")
            await self.close_pool()
            print(">>> 작업 완료")

async def main():
    """메인 함수"""
    if not BOT_TOKEN:
        print(">>> DISCORD_TOKEN 환경변수가 없습니다")
        return
    
    if not DATABASE_URL:
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