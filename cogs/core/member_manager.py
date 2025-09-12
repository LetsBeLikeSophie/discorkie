import os
import re
import csv
import discord
from discord import Interaction, app_commands
from discord.ext import commands
import asyncio
from typing import List, Dict, Any

CHANNEL_ID = 1275111651493806150
ALLOWED_ID = [
    1111599410594467862,  # 비수긔
    133478670034665473,  # 딸기
    # 추가하고 싶은 다른 사용자 ID들을 여기에 넣으세요 
    # 123456789012345678,  # 다른 사용자 예시
]
DATA_PATH = os.path.join("data", "levels.csv")
TARGET_ROLE_ID = 1329456061048164454  # 정리할 역할 ID = 기웃대는 주민
# TARGET_ROLE_ID = 1412361616888172634  # 개발 테스트용
# TARGET_ROLE_ID = 1411679460310122536  # 운영 테스트용

# DM 메시지 상수
FAREWELL_MESSAGE = "안녕하세요! **{guild_name}** 길드에서 인사드려요!😊\n\n길드 정리 작업으로 인해 서버에서 나가시게 되었어요.\n언제든지 다시 돌아오시면 환영이에요!\n함께했던 시간 고마웠고, 나중에 또 만나요!\n\n*우당탕탕 스톰윈드 지구대 드림*"

class MemberManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # 레벨스캔 주석처리
    # @app_commands.command(
    #     name="레벨스캔",
    #     description="일부 사용자만 사용할 수 있어요."
    # )
    # async def level_scan(self, interaction: Interaction):
    #     # 레벨스캔 로직 주석처리
    #     pass

    def analyze_target_members(self, guild: discord.Guild, target_role: discord.Role) -> Dict[str, List[discord.Member]]:
        """대상 멤버들을 분석하여 분류"""
        LOG_PREFIX = "[MemberManager.analyze_target_members]"
        print(f"{LOG_PREFIX} 대상 멤버 분석 시작")
        
        # 해당 역할을 가진 모든 멤버 찾기
        all_target_members = [member for member in guild.members if target_role in member.roles]
        print(f"{LOG_PREFIX} 기웃거리는 주민 역할 보유자: {len(all_target_members)}명")
        
        # 역할 개수에 따라 분류
        single_role_members = []  # 기웃거리는 주민 역할만 가진 멤버
        multi_role_members = []   # 기웃거리는 주민 + 다른 역할도 가진 멤버
        
        for member in all_target_members:
            # @everyone 역할 제외하고 실제 역할 개수 계산
            actual_roles = [role for role in member.roles if role.name != "@everyone"]
            
            if len(actual_roles) == 1:  # 기웃거리는 주민 역할만
                single_role_members.append(member)
                print(f"{LOG_PREFIX} 단일역할: {member.display_name}")
            else:  # 다른 역할도 있음
                multi_role_members.append(member)
                other_roles = [role.name for role in actual_roles if role != target_role]
                print(f"{LOG_PREFIX} 다중역할: {member.display_name} (추가역할: {', '.join(other_roles)})")
        
        print(f"{LOG_PREFIX} 분석 완료 - 단일역할: {len(single_role_members)}명, 다중역할: {len(multi_role_members)}명")
        
        return {
            "single_role": single_role_members,
            "multi_role": multi_role_members,
            "all_target": all_target_members
        }

    @app_commands.command(
        name="기웃정리", 
        description="특정 역할을 가진 멤버들을 서버에서 정리합니다 (관리자 전용)"
    )
    async def kick_cleanup(self, interaction: Interaction):
        LOG_PREFIX = "[MemberManager.kick_cleanup]"
        print(f"{LOG_PREFIX} 기웃정리 명령어 실행 시작 - 사용자: {interaction.user.name}")
        
        if interaction.user.id not in ALLOWED_ID:
            print(f"{LOG_PREFIX} 권한 없는 사용자 접근 차단: {interaction.user.id}")
            return await interaction.response.send_message(
                "이 명령어는 관리자만 사용할 수 있어요!", ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        # 길드와 역할 확인
        guild = interaction.guild
        if not guild:
            print(f"{LOG_PREFIX} 길드 정보 없음")
            return await interaction.followup.send("길드 정보를 찾을 수 없어요!")
        
        target_role = guild.get_role(TARGET_ROLE_ID)
        if not target_role:
            print(f"{LOG_PREFIX} 대상 역할을 찾을 수 없음: {TARGET_ROLE_ID}")
            return await interaction.followup.send("대상 역할을 찾을 수 없어요!")
        
        print(f"{LOG_PREFIX} 대상 역할 확인: {target_role.name}")
        
        # 멤버 분석
        member_analysis = self.analyze_target_members(guild, target_role)
        
        single_role_members = member_analysis["single_role"]
        multi_role_members = member_analysis["multi_role"]
        
        if not single_role_members and not multi_role_members:
            print(f"{LOG_PREFIX} 정리할 멤버 없음")
            return await interaction.followup.send("정리할 멤버가 없어요!")
        
        # 확인 메시지 구성
        confirm_msg = f"**기웃정리 대상: 총 {len(single_role_members) + len(multi_role_members)}명**\n\n"
        confirm_msg += f"기웃역할만: {len(single_role_members)}명\n"
        confirm_msg += f"기웃역할+기타: {len(multi_role_members)}명\n\n"
        confirm_msg += f"**상세 목록:**\n"

        # 전체 대상 목록 표시
        all_members = single_role_members + multi_role_members
        if len(all_members) <= 15:
            for member in all_members:
                if member in multi_role_members:
                    other_roles = [role.name for role in member.roles 
                                 if role.name != "@everyone" and role != target_role]
                    confirm_msg += f"- {member.display_name} (+{', '.join(other_roles)})\n"
                else:
                    confirm_msg += f"- {member.display_name}\n"
        else:
            for member in all_members[:12]:
                if member in multi_role_members:
                    other_roles = [role.name for role in member.roles 
                                 if role.name != "@everyone" and role != target_role]
                    confirm_msg += f"- {member.display_name} (+{', '.join(other_roles)})\n"
                else:
                    confirm_msg += f"- {member.display_name}\n"
            confirm_msg += f"... 외 {len(all_members) - 12}명\n"

        confirm_msg += "\n**어떻게 처리할까요?** (60초 후 자동 취소)"
        
        # 옵션 버튼 뷰
        view = CleanupOptionsView(member_analysis, guild.name, target_role.name)
        
        print(f"{LOG_PREFIX} 사용자에게 옵션 선택 화면 표시")
        await interaction.followup.send(confirm_msg, view=view, ephemeral=True)


class CleanupOptionsView(discord.ui.View):
    def __init__(self, member_analysis: Dict[str, List[discord.Member]], guild_name: str, target_role_name: str):
        super().__init__(timeout=60)
        self.member_analysis = member_analysis
        self.guild_name = guild_name
        self.target_role_name = target_role_name
        self.LOG_PREFIX = "[CleanupOptionsView]"
        
        # 동적으로 버튼 생성
        self.clear_items()  # 기존 버튼 제거
        
        # 기웃 X명 추방 버튼
        basic_button = discord.ui.Button(
            label=f"기웃 {len(member_analysis['single_role'])}명 추방",
            style=discord.ButtonStyle.primary,
            row=0
        )
        basic_button.callback = self.basic_cleanup
        self.add_item(basic_button)
        
        # X명 모두 추방 버튼  
        full_button = discord.ui.Button(
            label=f"{len(member_analysis['all_target'])}명 모두 추방",
            style=discord.ButtonStyle.danger,
            row=0
        )
        full_button.callback = self.full_cleanup
        self.add_item(full_button)
        
        # 역할만 정리 버튼
        role_button = discord.ui.Button(
            label="역할만 정리",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        role_button.callback = self.role_only_cleanup
        self.add_item(role_button)
        
        # 취소 버튼
        cancel_button = discord.ui.Button(
            label="취소",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        cancel_button.callback = self.cancel_cleanup
        self.add_item(cancel_button)
        
        print(f"{self.LOG_PREFIX} 옵션 뷰 생성 완료")
        
    async def basic_cleanup(self, interaction: discord.Interaction):
        """기웃거리는 주민만 있는 멤버만 추방 + 다중역할 멤버 리스트 표시"""
        print(f"{self.LOG_PREFIX} 기본 정리 옵션 선택됨")
        
        await interaction.response.defer(ephemeral=True)
        
        single_role_members = self.member_analysis["single_role"]
        multi_role_members = self.member_analysis["multi_role"]
        
        if not single_role_members:
            await interaction.followup.send("추방할 단일 역할 멤버가 없어요!")
            return
        
        # 추방 실행
        result = await self.execute_kicks(single_role_members, interaction, "기본 정리")
        
        # 결과 메시지에 다중 역할 멤버 정보 추가
        result_msg = result + "\n\n"
        
        if multi_role_members:
            result_msg += f"⚠️ **처리되지 않은 다중 역할 멤버** ({len(multi_role_members)}명)\n"
            result_msg += "*이 멤버들은 다른 역할도 가지고 있어 추방되지 않았어요*\n\n"
            
            for member in multi_role_members[:10]:
                other_roles = [role.name for role in member.roles 
                             if role.name != "@everyone" and self.target_role_name not in role.name]
                result_msg += f"- {member.display_name} (+{', '.join(other_roles)})\n"
            
            if len(multi_role_members) > 10:
                result_msg += f"... 외 {len(multi_role_members) - 10}명\n"
        
        await interaction.edit_original_response(content=result_msg, view=None)

    async def full_cleanup(self, interaction: discord.Interaction):
        """모든 대상 멤버 추방 (다중 역할 포함)"""
        print(f"{self.LOG_PREFIX} 전체 추방 옵션 선택됨")
        
        await interaction.response.defer(ephemeral=True)
        
        all_members = self.member_analysis["all_target"]
        
        if not all_members:
            await interaction.followup.send("추방할 멤버가 없어요!")
            return
        
        # 경고 메시지
        warning_msg = f"⚠️ **주의: 전체 추방 모드**\n"
        warning_msg += f"기웃거리는 주민 외 다른 역할을 가진 멤버들도 모두 추방됩니다!\n"
        warning_msg += f"총 {len(all_members)}명이 추방됩니다.\n\n"
        warning_msg += "정말로 진행하시겠습니까?"
        
        # 최종 확인 뷰
        confirm_view = FinalConfirmView(all_members, self.guild_name, "전체 추방")
        await interaction.followup.send(warning_msg, view=confirm_view, ephemeral=True)

    async def role_only_cleanup(self, interaction: discord.Interaction):
        """다중 역할 멤버는 역할만 제거, 단일 역할은 추방"""
        print(f"{self.LOG_PREFIX} 역할만 제거 옵션 선택됨")
        
        await interaction.response.defer(ephemeral=True)
        
        single_role_members = self.member_analysis["single_role"]
        multi_role_members = self.member_analysis["multi_role"]
        
        processing_msg = "역할 제거 및 추방 처리 중...\n\n"
        await interaction.edit_original_response(content=processing_msg, view=None)
        
        # 결과 카운터
        kick_success = 0
        kick_failed = 0
        role_remove_success = 0
        role_remove_failed = 0
        dm_success = 0
        dm_failed = 0
        
        # 1. 단일 역할 멤버들 추방
        if single_role_members:
            print(f"{self.LOG_PREFIX} 단일 역할 멤버 {len(single_role_members)}명 추방 시작")
            
            for i, member in enumerate(single_role_members, 1):
                try:
                    # DM 발송
                    try:
                        farewell_message = FAREWELL_MESSAGE.format(guild_name=self.guild_name)
                        await member.send(farewell_message)
                        dm_success += 1
                        print(f"{self.LOG_PREFIX} DM 성공: {member.display_name}")
                    except:
                        dm_failed += 1
                        print(f"{self.LOG_PREFIX} DM 실패: {member.display_name}")
                    
                    await asyncio.sleep(1)
                    
                    # 추방
                    await member.kick(reason="길드 정리 작업 - 역할만 제거 모드")
                    kick_success += 1
                    print(f"{self.LOG_PREFIX} 추방 성공: {member.display_name}")
                    
                except Exception as e:
                    kick_failed += 1
                    print(f"{self.LOG_PREFIX} 추방 실패: {member.display_name} - {e}")
                
                # 진행상황 업데이트
                if i % 3 == 0:
                    progress = f"역할 제거 및 추방 처리 중... ({i}/{len(single_role_members) + len(multi_role_members)})"
                    try:
                        await interaction.edit_original_response(content=progress)
                    except:
                        pass
                
                await asyncio.sleep(0.5)
        
        # 2. 다중 역할 멤버들 역할만 제거
        if multi_role_members:
            print(f"{self.LOG_PREFIX} 다중 역할 멤버 {len(multi_role_members)}명 역할 제거 시작")
            
            target_role_id = TARGET_ROLE_ID
            
            for i, member in enumerate(multi_role_members, len(single_role_members) + 1):
                try:
                    # 해당 역할 찾기
                    target_role = None
                    for role in member.roles:
                        if role.id == target_role_id:
                            target_role = role
                            break
                    
                    if target_role:
                        await member.remove_roles(target_role, reason="길드 정리 작업 - 역할만 제거")
                        role_remove_success += 1
                        print(f"{self.LOG_PREFIX} 역할 제거 성공: {member.display_name}")
                    else:
                        role_remove_failed += 1
                        print(f"{self.LOG_PREFIX} 대상 역할 없음: {member.display_name}")
                    
                except Exception as e:
                    role_remove_failed += 1
                    print(f"{self.LOG_PREFIX} 역할 제거 실패: {member.display_name} - {e}")
                
                # 진행상황 업데이트
                if i % 3 == 0:
                    progress = f"역할 제거 및 추방 처리 중... ({i}/{len(single_role_members) + len(multi_role_members)})"
                    try:
                        await interaction.edit_original_response(content=progress)
                    except:
                        pass
                
                await asyncio.sleep(0.3)
        
        # 최종 결과
        result_msg = f"**역할만 제거 모드 완료!** 🎉\n\n"
        result_msg += f"🔥 **추방 결과**\n"
        result_msg += f"- 성공: {kick_success}명\n"
        result_msg += f"- 실패: {kick_failed}명\n\n"
        result_msg += f"⚙️ **역할 제거 결과**\n"
        result_msg += f"- 성공: {role_remove_success}명\n"
        result_msg += f"- 실패: {role_remove_failed}명\n\n"
        result_msg += f"📧 **DM 발송**\n"
        result_msg += f"- 성공: {dm_success}명\n"
        result_msg += f"- 실패: {dm_failed}명\n\n"
        result_msg += "모든 작업이 완료되었어요!"
        
        print(f"{self.LOG_PREFIX} 역할만 제거 모드 완료 - 추방:{kick_success}, 역할제거:{role_remove_success}")
        await interaction.edit_original_response(content=result_msg, view=None)

    async def cancel_cleanup(self, interaction: discord.Interaction):
        print(f"{self.LOG_PREFIX} 기웃정리 취소됨")
        await interaction.response.edit_message(
            content="기웃정리가 취소되었어요.", 
            view=None
        )

    async def execute_kicks(self, members_to_kick: List[discord.Member], interaction: discord.Interaction, mode_name: str) -> str:
        """멤버 추방 실행"""
        print(f"{self.LOG_PREFIX} {mode_name} 추방 시작: {len(members_to_kick)}명")
        
        success_count = 0
        dm_success_count = 0
        dm_failed_count = 0
        kick_failed_count = 0
        
        farewell_message = FAREWELL_MESSAGE.format(guild_name=self.guild_name)
        
        for i, member in enumerate(members_to_kick, 1):
            try:
                # DM 발송 시도
                try:
                    await member.send(farewell_message)
                    dm_success_count += 1
                    print(f"{self.LOG_PREFIX} DM 성공: {member.display_name}")
                except discord.Forbidden:
                    dm_failed_count += 1
                    print(f"{self.LOG_PREFIX} DM 실패 (차단됨): {member.display_name}")
                except Exception as e:
                    dm_failed_count += 1
                    print(f"{self.LOG_PREFIX} DM 실패: {member.display_name} - {e}")
                
                await asyncio.sleep(1)
                
                # 추방 시도
                try:
                    await member.kick(reason=f"길드 정리 작업 - {mode_name}")
                    success_count += 1
                    print(f"{self.LOG_PREFIX} 추방 성공: {member.display_name}")
                except discord.Forbidden:
                    kick_failed_count += 1
                    print(f"{self.LOG_PREFIX} 추방 실패 (권한부족): {member.display_name}")
                except Exception as e:
                    kick_failed_count += 1
                    print(f"{self.LOG_PREFIX} 추방 실패: {member.display_name} - {e}")
                
                # 진행상황 업데이트
                if i % 5 == 0 or i == len(members_to_kick):
                    progress_msg = f"{mode_name} 처리 중... ({i}/{len(members_to_kick)})"
                    try:
                        await interaction.edit_original_response(content=progress_msg)
                    except:
                        pass
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"{self.LOG_PREFIX} 처리 중 오류: {member.display_name} - {e}")
                continue
        
        # 결과 메시지 생성
        result_msg = f"**{mode_name} 완료!** 🎉\n\n"
        result_msg += f"📊 **처리 결과**\n"
        result_msg += f"- 대상 인원: {len(members_to_kick)}명\n"
        result_msg += f"- 추방 성공: {success_count}명\n"
        result_msg += f"- 추방 실패: {kick_failed_count}명\n\n"
        result_msg += f"💌 **DM 발송 결과**\n"
        result_msg += f"- DM 성공: {dm_success_count}명\n"
        result_msg += f"- DM 실패: {dm_failed_count}명"
        
        print(f"{self.LOG_PREFIX} {mode_name} 완료 - 성공:{success_count}, 실패:{kick_failed_count}")
        
        return result_msg

    async def on_timeout(self):
        print(f"{self.LOG_PREFIX} 선택 시간 초과")
        # 타임아웃 시 버튼 비활성화
        for item in self.children:
            item.disabled = True


class FinalConfirmView(discord.ui.View):
    """전체 추방 최종 확인 뷰"""
    def __init__(self, members_to_kick: List[discord.Member], guild_name: str, mode_name: str):
        super().__init__(timeout=30)
        self.members_to_kick = members_to_kick
        self.guild_name = guild_name
        self.mode_name = mode_name
        self.LOG_PREFIX = "[FinalConfirmView]"
        
    @discord.ui.button(label="확실히 진행", style=discord.ButtonStyle.danger)
    async def final_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"{self.LOG_PREFIX} 전체 추방 최종 확인됨")
        
        await interaction.response.defer(ephemeral=True)
        
        # CleanupOptionsView의 execute_kicks 메서드 재사용
        cleanup_view = CleanupOptionsView({}, self.guild_name, "")
        result = await cleanup_view.execute_kicks(self.members_to_kick, interaction, self.mode_name)
        
        await interaction.edit_original_response(content=result, view=None)
    
    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def final_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"{self.LOG_PREFIX} 전체 추방 취소됨")
        await interaction.response.edit_message(
            content="전체 추방이 취소되었어요.", 
            view=None
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberManager(bot))