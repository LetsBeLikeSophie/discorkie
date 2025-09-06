#!/usr/bin/env python3
"""
emoji_replacer.py

디스코드 서버에서 특정 이모티콘을 다른 이모티콘으로 일괄 변경하는 스크립트
"""
import discord
import asyncio
import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드

# 설정값
GUILD_ID = 1275099769731022971  # 서버 ID
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

class EmojiReplacer:
    def __init__(self):
        self.bot = None
        self.guild = None
        
    async def connect_to_discord(self):
        """디스코드 봇 연결"""
        intents = discord.Intents.default()
        intents.members = True
        
        self.bot = discord.Client(intents=intents)
        
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
        
        bot_task = asyncio.create_task(self.bot.start(BOT_TOKEN))
        
        try:
            await asyncio.wait_for(ready_future, timeout=30.0)
            print(">>> 디스코드 연결 완료")
        except asyncio.TimeoutError:
            print(">>> 디스코드 연결 타임아웃")
            bot_task.cancel()
            raise
        except Exception as e:
            print(f">>> 디스코드 연결 오류: {e}")
            bot_task.cancel()
            raise

    async def find_members_with_emoji(self, target_emoji: str) -> List[discord.Member]:
        """특정 이모티콘이 붙은 멤버들 찾기"""
        if not self.guild:
            return []
        
        matching_members = []
        for member in self.guild.members:
            if member.bot:
                continue
                
            if member.display_name.startswith(target_emoji):
                matching_members.append(member)
        
        print(f">>> {target_emoji} 이모티콘이 붙은 멤버 {len(matching_members)}명 발견")
        for i, member in enumerate(matching_members[:10], 1):  # 처음 10명만 출력
            print(f">>>   [{i}] {member.display_name}")
        
        if len(matching_members) > 10:
            print(f">>>   ... 외 {len(matching_members) - 10}명")
        
        return matching_members

    async def replace_emoji_batch(self, old_emoji: str, new_emoji: str, dry_run: bool = True) -> Dict[str, int]:
        """이모티콘 일괄 변경"""
        if not self.guild:
            return {"error": 1}
        
        # 대상 멤버 찾기
        target_members = await self.find_members_with_emoji(old_emoji)
        
        if not target_members:
            print(f">>> {old_emoji} 이모티콘이 붙은 멤버가 없어요")
            return {"found": 0}
        
        # 미리보기 모드
        if dry_run:
            print(f"\n>>> 미리보기 모드 (실제 변경 안함)")
            print(f">>> {old_emoji} → {new_emoji} 변경 예정:")
            for i, member in enumerate(target_members, 1):
                old_name = member.display_name
                new_name = old_name.replace(old_emoji, new_emoji, 1)  # 첫 번째만 변경
                print(f">>>   [{i}] {old_name} → {new_name}")
            
            print(f"\n>>> 총 {len(target_members)}명 변경 예정")
            print(f">>> 실제 변경하려면 dry_run=False로 다시 실행하세요")
            return {"preview": len(target_members)}
        
        # 실제 변경 수행
        print(f"\n>>> 실제 변경 시작: {old_emoji} → {new_emoji}")
        
        success_count = 0
        error_count = 0
        permission_error_count = 0
        
        for i, member in enumerate(target_members, 1):
            try:
                old_name = member.display_name
                new_name = old_name.replace(old_emoji, new_emoji, 1)  # 첫 번째만 변경
                
                await member.edit(nick=new_name)
                success_count += 1
                print(f">>> [{i}/{len(target_members)}] 성공: {old_name} → {new_name}")
                
                # API 제한을 위한 대기
                await asyncio.sleep(0.5)
                
            except discord.Forbidden:
                permission_error_count += 1
                print(f">>> [{i}/{len(target_members)}] 권한 부족: {member.display_name}")
            except Exception as e:
                error_count += 1
                print(f">>> [{i}/{len(target_members)}] 오류: {member.display_name} - {e}")
        
        print(f"\n>>> 변경 완료!")
        print(f">>> 성공: {success_count}명")
        print(f">>> 권한 부족: {permission_error_count}명") 
        print(f">>> 기타 오류: {error_count}명")
        
        return {
            "success": success_count,
            "permission_error": permission_error_count,
            "error": error_count
        }

    async def interactive_mode(self):
        """대화형 모드"""
        print("\n" + "="*50)
        print("    이모티콘 일괄 변경 도구")
        print("="*50)
        
        while True:
            print(f"\n현재 서버: {self.guild.name}")
            print("1. 이모티콘 변경")
            print("2. 특정 이모티콘 멤버 조회")
            print("3. 종료")
            
            choice = input("\n선택 (1-3): ").strip()
            
            if choice == "1":
                await self.change_emoji_interactive()
            elif choice == "2":
                await self.view_emoji_members()
            elif choice == "3":
                print(">>> 종료합니다")
                break
            else:
                print(">>> 잘못된 선택입니다")

    async def change_emoji_interactive(self):
        """이모티콘 변경 대화형"""
        print("\n--- 이모티콘 변경 ---")
        
        # 기존 이모티콘 입력
        old_emoji = input("변경할 이모티콘 입력 (예: ❓): ").strip()
        if not old_emoji:
            print(">>> 이모티콘을 입력해주세요")
            return
        
        # 새 이모티콘 입력  
        new_emoji = input("새로운 이모티콘 입력 (예: ⭐): ").strip()
        if not new_emoji:
            print(">>> 새 이모티콘을 입력해주세요")
            return
        
        # 미리보기 실행
        print(f"\n>>> {old_emoji} → {new_emoji} 변경 미리보기...")
        result = await self.replace_emoji_batch(old_emoji, new_emoji, dry_run=True)
        
        if result.get("found") == 0:
            return
        
        # 확인
        confirm = input(f"\n정말로 변경하시겠습니까? (y/N): ").strip().lower()
        if confirm in ['y', 'yes']:
            await self.replace_emoji_batch(old_emoji, new_emoji, dry_run=False)
        else:
            print(">>> 취소되었습니다")

    async def view_emoji_members(self):
        """특정 이모티콘 멤버 조회"""
        print("\n--- 이모티콘 멤버 조회 ---")
        emoji = input("조회할 이모티콘 입력: ").strip()
        if not emoji:
            print(">>> 이모티콘을 입력해주세요")
            return
        
        await self.find_members_with_emoji(emoji)

    async def run(self):
        """메인 실행 함수"""
        try:
            print(">>> 이모티콘 일괄 변경 스크립트 시작")
            
            # 디스코드 연결
            await self.connect_to_discord()
            
            if not self.guild:
                raise Exception("길드 연결 실패")
            
            # 대화형 모드 시작
            await self.interactive_mode()
            
        except Exception as e:
            print(f">>> 실행 오류: {e}")
        finally:
            if self.bot and not self.bot.is_closed():
                await self.bot.close()
                print(">>> 디스코드 연결 종료")

# 간단한 사용 예시 함수들
async def quick_replace(old_emoji: str, new_emoji: str, dry_run: bool = True):
    """빠른 변경 함수"""
    replacer = EmojiReplacer()
    try:
        await replacer.connect_to_discord()
        result = await replacer.replace_emoji_batch(old_emoji, new_emoji, dry_run)
        return result
    finally:
        if replacer.bot and not replacer.bot.is_closed():
            await replacer.bot.close()

async def main():
    """메인 함수"""
    if not BOT_TOKEN:
        print(">>> DISCORD_TOKEN 환경변수가 없습니다")
        return
    
    replacer = EmojiReplacer()
    await replacer.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n>>> 사용자에 의한 중단")
    except Exception as e:
        print(f">>> 예상치 못한 오류: {e}")