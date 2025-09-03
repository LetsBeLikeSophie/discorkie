import discord
from discord.ext import commands
from discord import app_commands, Interaction
import os
from db.database_manager import db

def find_character_server(character_name):
    """member.txt에서 캐릭터명으로 서버 찾기"""
    try:
        file_path = "member.txt"
        if not os.path.exists(file_path):
            print(f">>> member.txt 파일이 없음")
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            if "-" not in line:
                continue
            name, slug = line.strip().split("-", 1)
            if name == character_name:
                print(f">>> 캐릭터 서버 발견: {character_name} -> {slug}")
                return slug
        
        print(f">>> 캐릭터 서버 못찾음: {character_name}")
        return None
        
    except Exception as e:
        print(f">>> 캐릭터 서버 찾기 오류: {e}")
        return None

async def handle_raid_signup(interaction: Interaction, event_id: int, raid_view):
    """레이드 신청 처리 메인 함수"""
    try:
        print(f">>> 레이드 신청 처리 시작: 사용자 {interaction.user.id}, 이벤트 {event_id}")
        
        discord_id = str(interaction.user.id)
        current_nickname = interaction.user.display_name
        
        # 1. 기존 캐릭터 정보 확인
        character = await db.get_user_character(discord_id)
        
        if character:
            print(f">>> 기존 캐릭터 있음: {character['character_name']}")
            
            # 닉네임이 바뀌었는지 확인
            if character['character_name'] != current_nickname:
                print(f">>> 닉네임 변경 감지: {character['character_name']} -> {current_nickname}")
                await interaction.response.send_message(
                    f"⚠️ **닉네임이 변경되었습니다**\n"
                    f"기존 신청: **{character['character_name']}** ({character['realm_slug']})\n"
                    f"현재 닉네임: **{current_nickname}**\n\n"
                    f"현재 캐릭터로 신청하려면 `/닉 {character['character_name']}` 명령어로 닉네임을 되돌리거나\n"
                    f"새 캐릭터로 신청하려면 기존 신청을 먼저 취소해주세요.",
                    ephemeral=True
                )
                return
            
            # 기존 캐릭터로 바로 신청
            success = await db.signup_event(event_id, discord_id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ **{character['character_name']}**({character['realm_slug']})로 참가 신청 완료!\n"
                    f"🎯 역할: {character['character_role'] or '미설정'}",
                    ephemeral=True
                )
                await raid_view.update_raid_message(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 참가 신청에 실패했습니다. (이미 신청했거나 다른 오류)",
                    ephemeral=True
                )
            return
        
        # 2. 캐릭터 없음 - 디스코드 닉네임으로 자동 찾기 시도
        print(f">>> 디스코드 닉네임으로 자동 찾기: {current_nickname}")
        
        found_server = find_character_server(current_nickname)
        
        if found_server:
            print(f">>> 자동으로 캐릭터 정보 찾음: {current_nickname}@{found_server}")
            
            # 사용자 생성
            await db.get_or_create_user(discord_id, current_nickname)
            
            # 자동으로 캐릭터 생성
            success = await db.set_character(
                discord_id,
                current_nickname,
                found_server,
                None,  # 직업 미설정
                None,  # 전문화 미설정
                None   # 역할 미설정
            )
            
            if success:
                # 바로 레이드 신청
                signup_success = await db.signup_event(event_id, discord_id)
                
                if signup_success:
                    await interaction.response.send_message(
                        f"🎉 **자동 캐릭터 생성 및 참가 신청 완료!**\n"
                        f"🧙‍♂️ **{current_nickname}** ({found_server})\n"
                        f"⚠️ 직업/역할은 나중에 수정 가능합니다.",
                        ephemeral=True
                    )
                    await raid_view.update_raid_message(interaction)
                else:
                    await interaction.response.send_message(
                        f"✅ 캐릭터는 생성되었지만 레이드 신청에 실패했습니다.\n"
                        f"🧙‍♂️ **{current_nickname}** ({found_server})",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ 자동 캐릭터 생성에 실패했습니다.",
                    ephemeral=True
                )
        else:
            print(f">>> 자동 찾기 실패")
            # 자동으로 못찾음
            await interaction.response.send_message(
                f"❌ **캐릭터 정보를 찾을 수 없습니다**\n"
                f"디스코드 닉네임 `{current_nickname}`으로 길드 멤버를 찾지 못했습니다.\n"
                f"`/닉 캐릭터명` 명령어로 정확한 길드 캐릭터명으로 닉네임을 변경한 후 다시 시도해주세요.",
                ephemeral=True
            )
            
    except Exception as e:
        print(f">>> 레이드 신청 처리 오류: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ 오류가 발생했습니다. 관리자에게 문의해주세요.",
                ephemeral=True
            )

class CharacterManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(CharacterManager(bot))