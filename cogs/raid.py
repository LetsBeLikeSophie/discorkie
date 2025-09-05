from discord.ext import commands
from discord import app_commands, Interaction, ui
import discord
import os
import asyncpg
from decorators.guild_only import guild_only
from utils.character_validator import validate_character, get_character_info
from dotenv import load_dotenv

load_dotenv()

# 서버 목록 (한국어 → 영어 매핑)
SERVER_LIST = {
    "아즈샤라": "Azshara",
    "하이잘": "Hyjal",
    "굴단": "Gul'dan",
    "데스윙": "Deathwing",
    "불타는군단": "Burning Legion",
    "스톰레이지": "Stormrage",
    "윈드러너": "Windrunner",
    "줄진": "Zul'jin",
    "달라란": "Dalaran",
    "두로탄": "Durotan",
    "말퓨리온": "Malfurion",
    "헬스크림": "Hellscream",
    "세나리우스": "Cenarius",
    "와일드해머": "Wildhammer",
    "렉사르": "Rexxar",
    "알렉스트라자": "Alexstrasza",
    "가로나": "Garona"
}

async def save_character_to_db(char_info: dict, user: discord.Member, is_guild_member: bool = False) -> bool:
    """캐릭터 정보를 characters 테이블에 저장"""
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            print(">>> DATABASE_URL 환경변수가 없습니다")
            return False
        
        conn = await asyncpg.connect(database_url)
        
        name = char_info.get("name")
        realm = char_info.get("realm")
        
        if not name or not realm:
            print(f">>> 필수 데이터 누락: name={name}, realm={realm}")
            await conn.close()
            return False
        
        # raider.io API 응답값 그대로 사용
        race = char_info.get("race", "")
        class_name = char_info.get("class", "")
        active_spec = char_info.get("active_spec_name", "")
        active_spec_role = char_info.get("active_spec_role", "")
        gender = char_info.get("gender", "")
        faction = char_info.get("faction", "")

        print(f">>> characters 테이블 저장 시도: {name}-{realm}")
        
        # characters 테이블에 캐릭터 정보만 저장
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
        name,
        realm,
        is_guild_member,
        race,
        class_name,
        active_spec,
        active_spec_role,
        gender,
        faction,
        char_info.get("achievement_points", 0),
        char_info.get("profile_url", ""),
        char_info.get("profile_banner", ""),
        char_info.get("thumbnail_url", ""),
        "kr"  # region
        )
        
        await conn.close()
        print(f">>> characters 테이블 저장 성공: {name}-{realm}")
        return True
        
    except Exception as e:
        print(f">>> characters 테이블 저장 오류: {e}")
        return False

async def link_character_to_discord(character_name: str, realm_slug: str, user: discord.Member) -> bool:
    """캐릭터를 디스코드 유저에게 연결"""
    try:
        database_url = os.getenv("DATABASE_URL")
        conn = await asyncpg.connect(database_url)
        
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
            await conn.close()
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
        
        await conn.close()
        print(f">>> 디스코드 연결 성공: {character_name}-{realm_slug} -> {discord_username}#{discord_id}")
        return True
        
    except Exception as e:
        print(f">>> 디스코드 연결 오류: {e}")
        return False

class DBServerSelectView(ui.View):
    def __init__(self, character_name: str, server_options: list, user: discord.Member):
        super().__init__(timeout=60)
        self.character_name = character_name
        self.user = user
        
        # 서버 선택 드롭다운 생성
        select = discord.ui.Select(
            placeholder="서버를 선택해주세요",
            options=server_options
        )
        select.callback = self.server_select_callback
        self.add_item(select)

    async def server_select_callback(self, interaction: Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("본인만 선택할 수 있어요!", ephemeral=True)
            return
            
        selected_realm = interaction.data['values'][0]
        
        await interaction.response.send_message(
            f"🔄 **{self.character_name}-{selected_realm}** 정보를 업데이트하고 닉네임을 변경 중...",
            ephemeral=True
        )
        
        # 캐릭터를 디스코드 유저에게 연결
        success = await link_character_to_discord(self.character_name, selected_realm, self.user)
        
        if success:
            new_nickname_with_emoji = f"🚀{self.character_name}"
            try:
                await self.user.edit(nick=new_nickname_with_emoji)
                await interaction.followup.send(
                    f"✅ 닉네임이 **{new_nickname_with_emoji}**로 변경되었어요!\n"
                    f"🎮 서버: {selected_realm}",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ 권한이 부족해서 닉네임을 변경할 수 없어요!",
                    ephemeral=True
                )
            except Exception as e:
                print(f">>> 닉네임 변경 오류: {e}")
                await interaction.followup.send(
                    "❌ 닉네임 변경 중 오류가 발생했어요!",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                "⚠️ 캐릭터 연결 중 오류가 발생했어요!",
                ephemeral=True
            )
        
        self.stop()

class ServerSelectView(ui.View):
    def __init__(self, character_name: str, user: discord.Member):
        super().__init__(timeout=60)
        self.character_name = character_name
        self.user = user
        self.selected_server = None
        
        # 서버 선택 드롭다운 생성
        options = [
            discord.SelectOption(label=korean_name, value=english_name)
            for korean_name, english_name in SERVER_LIST.items()
        ]
        
        # 25개 제한으로 나누기 (필요시)
        select = discord.ui.Select(placeholder="서버를 선택해주세요", options=options[:25])
        select.callback = self.server_select_callback
        self.add_item(select)

    async def server_select_callback(self, interaction: Interaction):
        if interaction.user != self.user:
            await interaction.response.send_message("본인만 선택할 수 있어요!", ephemeral=True)
            return
            
        self.selected_server = interaction.data['values'][0]
        
        # 한국어 서버명 찾기
        korean_server = None
        for k, v in SERVER_LIST.items():
            if v == self.selected_server:
                korean_server = k
                break
        
        await interaction.response.send_message(
            f"🔄 **{korean_server}** 서버에서 **{self.character_name}** 캐릭터를 확인 중...", 
            ephemeral=True
        )
        
        # 캐릭터 유효성 검사
        is_valid = await validate_character(self.selected_server, self.character_name)
        
        if not is_valid:
            await interaction.followup.send(
                f"❌ **{self.character_name}-{korean_server}** 캐릭터를 찾을 수 없어요!\n"
                f"캐릭터명과 서버를 다시 확인해주세요.", 
                ephemeral=True
            )
            return
        
        # 캐릭터 정보 가져오기
        char_info = await get_character_info(self.selected_server, self.character_name)
        
        if not char_info:
            await interaction.followup.send(
                f"❌ 캐릭터 정보를 가져올 수 없어요!", 
                ephemeral=True
            )
            return
        
        # 🚀 이모티콘으로 닉네임 생성
        new_nickname = f"🚀{self.character_name}"
        
        print(f">>> 새 닉네임: {new_nickname}")
        
        # 캐릭터 데이터베이스 저장 시도
        char_save_success = await save_character_to_db(char_info, self.user, is_guild_member=False)
        
        # 디스코드 연결 시도
        link_success = await link_character_to_discord(self.character_name, self.selected_server, self.user)
        
        db_warning = ""
        if not (char_save_success and link_success):
            db_warning = "\n⚠️ 데이터베이스 처리 중 일부 오류가 발생했습니다."
        
        try:
            await self.user.edit(nick=new_nickname)
            role = char_info.get("active_spec_role", "DPS")
            await interaction.followup.send(
                f"✅ 닉네임이 **{new_nickname}**로 변경되었어요!\n"
                f"🎮 서버: {korean_server}\n"
                f"🏷️ 역할: {role}{db_warning}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ 권한이 부족해서 닉네임을 변경할 수 없어요!{db_warning}", 
                ephemeral=True
            )
        except Exception as e:
            print(f">>> 닉네임 변경 오류: {e}")
            await interaction.followup.send(
                f"❌ 닉네임 변경 중 오류가 발생했어요!{db_warning}", 
                ephemeral=True
            )
        
        self.stop()

class Raid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /닉
    @app_commands.command(name="닉", description="레이드 참가 캐릭터명으로!")
    @app_commands.describe(new_nickname="바꾸고 싶은 닉네임")
    # @guild_only() 
    async def change_nickname(self, interaction: Interaction, new_nickname: str):
        await interaction.response.defer(ephemeral=True)
        
        print(f">>> /닉 명령어 실행: 사용자 {interaction.user.display_name}, 요청 닉네임: {new_nickname}")
        
        # 특정 역할 ID 확인
        # special_role_id = 1329456061048164454 기웃대는주민
        special_role_id = 1412361616888172634  # 테스트용
        user_has_special_role = any(role.id == special_role_id for role in interaction.user.roles)
        
        print(f">>> 사용자 특수 역할 보유 여부: {user_has_special_role}")
        
        if user_has_special_role:
            # 서버 선택 UI 표시
            print(">>> 서버 선택 UI 표시")
            view = ServerSelectView(new_nickname, interaction.user)
            await interaction.followup.send("🌐 **서버를 선택해주세요:**", view=view, ephemeral=True)
            return
        
        else:
            # DB에서 서버 정보 조회 (새 테이블 구조 사용)
            print(">>> DB에서 서버 정보 조회 시도")
            try:
                database_url = os.getenv("DATABASE_URL")
                if not database_url:
                    await interaction.followup.send("❌ 데이터베이스 연결 설정이 없어요!", ephemeral=True)
                    return
                
                conn = await asyncpg.connect(database_url)
                
                # 길드 캐릭터 중에서 해당 이름으로 검색
                rows = await conn.fetch("""
                    SELECT DISTINCT character_name, realm_slug
                    FROM guild_bot.characters 
                    WHERE character_name = $1 AND is_guild_member = TRUE
                """, new_nickname)
                
                await conn.close()
                
                if not rows:
                    await interaction.followup.send(
                        f"❌ **{new_nickname}** 캐릭터를 길드 DB에서 찾을 수 없어요!\n"
                        "길드원만 이 기능을 사용할 수 있습니다.",
                        ephemeral=True
                    )
                    return
                
                if len(rows) == 1:
                    # 서버가 하나만 있는 경우
                    row = rows[0]
                    realm_slug = row['realm_slug']
                    print(f">>> 단일 서버 발견: {new_nickname}-{realm_slug}")
                    
                    success = await link_character_to_discord(new_nickname, realm_slug, interaction.user)
                    
                    if success:
                        new_nickname_with_emoji = f"🚀{new_nickname}"
                        try:
                            await interaction.user.edit(nick=new_nickname_with_emoji)
                            await interaction.followup.send(
                                f"✅ 닉네임이 **{new_nickname_with_emoji}**로 변경되었어요!\n"
                                f"🎮 서버: {realm_slug}",
                                ephemeral=True
                            )
                        except discord.Forbidden:
                            await interaction.followup.send(
                                "❌ 권한이 부족해서 닉네임을 변경할 수 없어요!", 
                                ephemeral=True
                            )
                        except Exception as e:
                            print(f">>> 닉네임 변경 오류: {e}")
                            await interaction.followup.send(
                                "❌ 닉네임 변경 중 오류가 발생했어요!", 
                                ephemeral=True
                            )
                    else:
                        await interaction.followup.send(
                            "⚠️ 캐릭터 연결 중 오류가 발생했어요!",
                            ephemeral=True
                        )
                        
                else:
                    # 서버가 여러 개인 경우
                    print(f">>> 다중 서버 발견: {len(rows)}개")
                    server_options = []
                    for row in rows:
                        realm_slug = row['realm_slug']
                        server_options.append(discord.SelectOption(
                            label=f"{new_nickname}-{realm_slug}",
                            value=realm_slug,
                            description=f"{realm_slug} 서버"
                        ))
                    
                    view = DBServerSelectView(new_nickname, server_options, interaction.user)
                    await interaction.followup.send(
                        f"🎮 **{new_nickname}** 캐릭터가 여러 서버에 있어요!\n"
                        "사용할 서버를 선택해주세요:",
                        view=view,
                        ephemeral=True
                    )
                    
            except Exception as e:
                print(f">>> DB 조회 오류: {e}")
                await interaction.followup.send(
                    "❌ 데이터베이스 조회 중 오류가 발생했어요!",
                    ephemeral=True
                )
                return

    @app_commands.command(name="심크", description="sim 명령어를 자동 생성해줘요!")
    @app_commands.describe(character_name="캐릭터 이름 (없으면 본인 서버닉네임 사용)")
    @guild_only() 
    async def sim_helper(self, interaction: Interaction, character_name: str = None):
        await interaction.response.defer(ephemeral=True)
        
        # 캐릭터명이 없으면 서버 닉네임 사용
        if not character_name:
            character_name = interaction.user.display_name

        file_path = "member.txt"
        if not os.path.exists(file_path):
            await interaction.followup.send("💾 member.txt 파일이 없어요!")
            return

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        found_server = None
        for line in lines:
            if "-" not in line:
                continue
            name, slug = line.strip().split("-", 1)
            if name == character_name:
                found_server = slug
                break

        if found_server:
            sim_params = f"kr {found_server} {character_name}"
            
            await interaction.followup.send(
                f"**🎮 {character_name}님의 sim 파라미터:**\n\n"
                f"**📋 아래를 복사해서 /sim 뒤에 붙여넣으세요:**\n"
                f"```{sim_params}```\n"
                f"🔍 서버: `{found_server}`"
            )
        else:
            await interaction.followup.send(
                f"❌ **{character_name}** 캐릭터를 찾을 수 없어요 😢\n"
                f"member.txt에 `{character_name}-서버명` 형태로 등록되어 있는지 확인해주세요!"
            )

# Cog 등록
async def setup(bot):
    await bot.add_cog(Raid(bot))