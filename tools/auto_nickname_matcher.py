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
        
    async def connect_to_discord(self):
        """디스코드 봇 연결"""
        intents = discord.Intents.default()
        intents.members = True
        
        self.bot = discord.Client(intents=intents)
        
        @self.bot.event
        async def on_ready():
            print(f">>> 봇 로그인 완료: {self.bot.user}")
            self.guild = self.bot.get_guild(GUILD_ID)
            if self.guild:
                print(f">>> 길드 연결 완료: {self.guild.name} (멤버수: {self.guild.member_count})")
            else:
                print(f">>> 길드를 찾을 수 없음: {GUILD_ID}")
        
        await self.bot.login(BOT_TOKEN)
        await self.bot.connect()
    
    async def get_characters_from_db(self):
        """DB에서 길드 캐릭터 목록 가져오기"""
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            
            rows = await conn.fetch("""
                SELECT character_name, realm_slug, id
                FROM guild_bot.characters 
                WHERE is_guild_member = TRUE
            """)
            
            await conn.close()
            
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
    
    async def link_character_to_discord_user(self, character_id: int, member: discord.Member):
        """캐릭터를 디스코드 유저에게 연결"""
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            
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
            
            await conn.close()
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
        
        print(">>> 멤버 처리 시작...")
        
        async for member in self.guild.fetch_members(limit=None):
            # 봇 건너뛰기
            if member.bot:
                continue
            
            processed_count += 1
            current_nickname = member.display_name
            
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
                print(f">>> 매칭 없음: {current_nickname}")
        
        print("\n>>> 처리 결과:")
        print(f">>> 총 처리된 멤버: {processed_count}")
        print(f">>> 성공: {success_count}")
        print(f">>> 건너뛰기 (이미 처리됨): {skip_count}")
        print(f">>> 오류: {error_count}")
        print(f">>> 매칭 없음: {processed_count - success_count - skip_count - error_count}")
    
    async def run(self):
        """메인 실행 함수"""
        try:
            print(">>> 자동 닉네임 매칭 시작")
            
            # 디스코드 연결
            await self.connect_to_discord()
            
            # 잠시 대기 (봇이 완전히 준비될 때까지)
            await asyncio.sleep(2)
            
            # 멤버 처리
            await self.process_members()
            
        except Exception as e:
            print(f">>> 실행 오류: {e}")
        finally:
            if self.bot:
                await self.bot.close()
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
    asyncio.run(main())