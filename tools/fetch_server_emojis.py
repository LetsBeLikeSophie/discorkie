#!/usr/bin/env python3
"""
tools/fetch_server_emojis.py

디스코드 서버의 WoW 관련 이모티콘을 수집하여 JSON 파일로 저장하는 스크립트
"""
import discord
import asyncio
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드

# 설정값
# GUILD_ID = 1275099769731022971  # 서버 ID
GUILD_ID = 1121105790477025310  # 서버 ID (테스트용)
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

class EmojisFetcher:
    def __init__(self):
        self.bot = None
        self.guild = None
        self.emojis_data = {}
        
    async def connect_to_discord(self):
        """디스코드 봇 연결"""
        intents = discord.Intents.default()
        intents.emojis_and_stickers = True
        
        self.bot = discord.Client(intents=intents)
        
        # 연결 완료 이벤트를 기다리기 위한 Future
        ready_future = asyncio.Future()
        
        @self.bot.event
        async def on_ready():
            print(f">>> 봇 로그인 완료: {self.bot.user}")
            self.guild = self.bot.get_guild(GUILD_ID)
            if self.guild:
                print(f">>> 길드 연결 완료: {self.guild.name}")
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
    
    async def fetch_wow_emojis(self):
        """WoW 관련 이모티콘 수집"""
        if not self.guild:
            print(">>> 길드가 연결되지 않음")
            return
        
        print(f">>> 서버 이모티콘 수집 시작: {self.guild.name}")
        print(f">>> 전체 이모티콘 수: {len(self.guild.emojis)}")
        
        wow_emojis = {}
        wow_classes = {}
        wow_roles = {}
        other_emojis = {}
        
        # WoW 직업 목록 (영문명)
        wow_class_names = [
            'warrior', 'paladin', 'hunter', 'rogue', 'priest', 'shaman',
            'mage', 'warlock', 'monk', 'druid', 'demonhunter', 'deathknight', 'evoker'
        ]
        
        # 역할 관련 키워드
        role_keywords = ['tank', 'heal', 'dps', 'damage']
        
        for emoji in self.guild.emojis:
            emoji_name = emoji.name.lower()
            emoji_id = str(emoji.id)
            emoji_format = f"<:{emoji.name}:{emoji.id}>"
            
            print(f">>> 처리 중: {emoji.name} (ID: {emoji.id})")
            
            # WoW 관련 이모티콘 필터링
            if emoji_name.startswith('wow_'):
                wow_emojis[emoji.name] = {
                    'id': emoji_id,
                    'format': emoji_format,
                    'name': emoji.name,
                    'animated': emoji.animated
                }
                
                # wow_ 접두사 제거한 이름
                clean_name = emoji_name.replace('wow_', '')
                
                # 직업 이모티콘인지 확인
                for class_name in wow_class_names:
                    if class_name in clean_name:
                        wow_classes[class_name] = {
                            'id': emoji_id,
                            'format': emoji_format,
                            'name': emoji.name,
                            'animated': emoji.animated
                        }
                        print(f">>>   WoW 직업 이모티콘 발견: {class_name} -> {emoji.name}")
                        break
                
                # 역할 이모티콘인지 확인
                for role_keyword in role_keywords:
                    if role_keyword in clean_name:
                        wow_roles[role_keyword] = {
                            'id': emoji_id,
                            'format': emoji_format,
                            'name': emoji.name,
                            'animated': emoji.animated
                        }
                        print(f">>>   WoW 역할 이모티콘 발견: {role_keyword} -> {emoji.name}")
                        break
            
            # 기타 유용한 이모티콘들
            elif any(keyword in emoji_name for keyword in ['check', 'cross', 'question', 'gear', 'sword', 'shield']):
                other_emojis[emoji.name] = {
                    'id': emoji_id,
                    'format': emoji_format,
                    'name': emoji.name,
                    'animated': emoji.animated
                }
        
        # 결과 저장
        self.emojis_data = {
            'guild_id': str(GUILD_ID),
            'guild_name': self.guild.name,
            'collected_at': discord.utils.utcnow().isoformat(),
            'wow_emojis': wow_emojis,
            'wow_classes': wow_classes,
            'wow_roles': wow_roles,
            'other_emojis': other_emojis,
            'total_count': len(wow_emojis) + len(other_emojis)
        }
        
        print(f">>> 수집 완료:")
        print(f">>>   WoW 이모티콘: {len(wow_emojis)}개")
        print(f">>>   WoW 직업: {len(wow_classes)}개")
        print(f">>>   WoW 역할: {len(wow_roles)}개")
        print(f">>>   기타 이모티콘: {len(other_emojis)}개")
        
    def save_to_file(self):
        """JSON 파일로 저장"""
        # data 폴더 생성
        data_dir = Path(__file__).parent.parent / 'data'
        data_dir.mkdir(exist_ok=True)
        
        # 파일 경로
        file_path = data_dir / 'server_emojis.json'
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.emojis_data, f, ensure_ascii=False, indent=2)
            
            print(f">>> 파일 저장 완료: {file_path}")
            print(f">>> 파일 크기: {file_path.stat().st_size} bytes")
            
        except Exception as e:
            print(f">>> 파일 저장 오류: {e}")
    
    def print_class_mapping(self):
        """직업 매핑 코드 출력"""
        if not self.emojis_data.get('wow_classes'):
            print(">>> WoW 직업 이모티콘이 없습니다")
            return
        
        print("\n>>> 생성된 직업 매핑 코드:")
        print("WOW_CLASS_EMOJIS = {")
        
        for class_name, emoji_data in self.emojis_data['wow_classes'].items():
            print(f'    "{class_name}": "{emoji_data["format"]}",')
        
        print("}")
        
    async def close(self):
        """봇 연결 종료"""
        if self.bot:
            await self.bot.close()
            print(">>> 봇 연결 종료")

async def main():
    """메인 실행 함수"""
    print(">>> 서버 이모티콘 수집 스크립트 시작")
    
    if not BOT_TOKEN:
        print(">>> 오류: DISCORD_TOKEN 환경변수가 설정되지 않음")
        return
    
    fetcher = EmojisFetcher()
    
    try:
        # 디스코드 연결
        await fetcher.connect_to_discord()
        
        # 이모티콘 수집
        await fetcher.fetch_wow_emojis()
        
        # 파일 저장
        fetcher.save_to_file()
        
        # 매핑 코드 출력
        fetcher.print_class_mapping()
        
    except Exception as e:
        print(f">>> 스크립트 실행 오류: {e}")
        import traceback
        print(f">>> 스택 추적: {traceback.format_exc()}")
        
    finally:
        # 정리
        await fetcher.close()

if __name__ == "__main__":
    asyncio.run(main())