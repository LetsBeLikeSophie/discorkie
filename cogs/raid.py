from discord.ext import commands
from discord import app_commands, Interaction, ForumChannel, ui
import discord
import datetime
import os
import aiohttp
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

# 번역 매핑
TRANSLATIONS = {
    "race": {
        "Human": "인간", "Orc": "오크", "Dwarf": "드워프", "Night Elf": "나이트 엘프",
        "Undead": "언데드", "Tauren": "타우렌", "Gnome": "노움", "Troll": "트롤",
        "Goblin": "고블린", "Blood Elf": "블러드 엘프", "Draenei": "드레나이",
        "Worgen": "늑대인간", "Pandaren": "판다렌", "Nightborne": "나이트본",
        "Highmountain Tauren": "높은산 타우렌", "Void Elf": "공허 엘프",
        "Lightforged Draenei": "빛벼림 드레나이", "Zandalari Troll": "잔달라 트롤",
        "Kul Tiran": "쿨 티란", "Dark Iron Dwarf": "검은무쇠 드워프",
        "Vulpera": "불페라", "Mag'har Orc": "마그하르 오크", "Mechagnome": "기계노움",
        "Dracthyr": "드랙티르", "Earthen": "토석인"
    },
    "class": {
        "Warrior": "전사", "Paladin": "성기사", "Hunter": "사냥꾼", "Rogue": "도적",
        "Priest": "사제", "Death Knight": "죽음의 기사", "Shaman": "주술사",
        "Mage": "마법사", "Warlock": "흑마법사", "Monk": "수도사", "Druid": "드루이드",
        "Demon Hunter": "악마사냥꾼", "Evoker": "기원사"
    },
    "spec": {
        "Arms": "무기", "Fury": "분노", "Protection": "방어", "Holy": "신성", 
        "Retribution": "징벌", "Beast Mastery": "야수", "Marksmanship": "사격",
        "Survival": "생존", "Assassination": "암살", "Outlaw": "무법", "Subtlety": "잠행",
        "Discipline": "수양", "Shadow": "암흑", "Blood": "혈기", "Frost": "냉기",
        "Unholy": "부정", "Elemental": "정기", "Enhancement": "고양", "Restoration": "복원",
        "Arcane": "비전", "Fire": "화염", "Affliction": "고통", "Demonology": "악마",
        "Destruction": "파괴", "Brewmaster": "양조", "Mistweaver": "운무", 
        "Windwalker": "풍운", "Balance": "조화", "Feral": "야성", "Guardian": "수호",
        "Havoc": "파멸", "Vengeance": "복수", "Devastation": "황폐", "Preservation": "보존",
        "Augmentation": "증강"
    },
    "gender": {
        "male": "남성", "female": "여성"
    },
    "faction": {
        "alliance": "얼라이언스", "horde": "호드"
    },
    "role": {
        "DPS": "딜", "TANK": "탱", "HEALING": "힐"
    },
    "realm": {
        "Hyjal": "하이잘", "Azshara": "아즈샤라", "Durotan": "듀로탄",
        "Zul'jin": "줄진", "Windrunner": "윈드러너", "Wildhammer": "와일드해머",
        "Rexxar": "렉사르", "Gul'dan": "굴단", "Deathwing": "데스윙",
        "Burning Legion": "불타는군단", "Stormrage": "스톰레이지", "Cenarius": "세나리우스",
        "Malfurion": "말퓨리온", "Hellscream": "헬스크림", "Dalaran": "달라란",
        "Garona": "가로나", "Alexstrasza": "알렉스트라자"
    }
}

def safe_lower(value):
    """안전하게 소문자로 변환"""
    return value.lower() if isinstance(value, str) else None

def translate_to_korean(category: str, english_value: str) -> str:
    """영문 값을 한국어로 번역"""
    if category in TRANSLATIONS:
        return TRANSLATIONS[category].get(english_value, english_value)
    return english_value

async def save_character_to_db(char_info: dict, language: str, user: discord.Member, is_guild_member: bool = False) -> bool:
    """캐릭터 정보를 데이터베이스에 저장"""
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
        
        # 디스코드 사용자 정보
        discord_id = str(user.id)
        discord_username = user.name
        
        # 언어에 따른 데이터 변환
        if language == "ko":
            race = translate_to_korean("race", char_info.get("race", ""))
            class_name = translate_to_korean("class", char_info.get("class", ""))
            active_spec = translate_to_korean("spec", char_info.get("active_spec_name", ""))
            active_spec_role = translate_to_korean("role", char_info.get("active_spec_role", ""))
            gender = translate_to_korean("gender", char_info.get("gender", ""))
            faction = translate_to_korean("faction", char_info.get("faction", ""))
            realm_display = translate_to_korean("realm", realm)
        else:
            race = char_info.get("race", "")
            class_name = safe_lower(char_info.get("class", ""))
            active_spec = safe_lower(char_info.get("active_spec_name", ""))
            active_spec_role = safe_lower(char_info.get("active_spec_role", ""))
            gender = safe_lower(char_info.get("gender", ""))
            faction = char_info.get("faction", "")
            realm_display = realm

        print(f">>> DB 저장 시도: {name}-{realm_display} ({language}) - 디스코드: {discord_username}#{discord_id}")
        
        # 데이터베이스에 삽입
        await conn.execute("""
            INSERT INTO guild_bot.guild_members (
                character_name, realm, is_guild_member,
                language, race, class, active_spec, active_spec_role,
                gender, faction, achievement_points,
                profile_url, profile_banner, thumbnail_url, region, last_crawled_at,
                discord_id, discord_username, is_discord_linked
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $15, NOW(),
                    $16, $17, $18)
            ON CONFLICT (character_name, realm, language)
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
                updated_at = NOW(),
                discord_id = EXCLUDED.discord_id,
                discord_username = EXCLUDED.discord_username,
                is_discord_linked = EXCLUDED.is_discord_linked
        """,
        name,
        realm_display,
        is_guild_member,
        language,
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
        "kr",  # region
        discord_id,
        discord_username,
        True  # is_discord_linked = True
        )
        
        await conn.close()
        print(f">>> DB 저장 성공: {name}-{realm_display} ({language}) - 디스코드: {discord_username}#{discord_id}")
        return True
        
    except Exception as e:
        print(f">>> DB 저장 오류: {e}")
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
        
        # 해당 행의 디스코드 정보 업데이트
        success = await self.update_discord_info_in_db(self.character_name, selected_realm, self.user)
        
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
                "⚠️ 데이터베이스 업데이트 중 오류가 발생했어요!",
                ephemeral=True
            )
        
        self.stop()

    async def update_discord_info_in_db(self, character_name: str, realm: str, user: discord.Member) -> bool:
        """DB에서 해당 캐릭터 행의 디스코드 정보를 업데이트"""
        try:
            database_url = os.getenv("DATABASE_URL")
            conn = await asyncpg.connect(database_url)
            
            discord_id = str(user.id)
            discord_username = user.name
            
            print(f">>> {character_name}-{realm}에 디스코드 정보 매핑")
            
            # 새로운 캐릭터의 한글/영어 레코드에 디스코드 정보 설정
            result = await conn.execute("""
                UPDATE guild_bot.guild_members 
                SET discord_id = $1, 
                    discord_username = $2,
                    updated_at = NOW()
                WHERE character_name = $3 AND realm = $4
            """, discord_id, discord_username, character_name, realm)
            
            await conn.close()
            print(f">>> DB 디스코드 매핑 완료: {character_name}-{realm} -> {discord_username}#{discord_id}")
            return True
            
        except Exception as e:
            print(f">>> DB 디스코드 매핑 오류: {e}")
            return False

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
        
        # 🚀 이모티콘으로 닉네임 생성 (공백 없음)
        new_nickname = f"🚀{self.character_name}"
        
        print(f">>> 새 닉네임: {new_nickname}")
        
        # 데이터베이스 저장 시도 (한글, 영문 모두)
        db_success_ko = await save_character_to_db(char_info, "ko", self.user, is_guild_member=False)
        db_success_en = await save_character_to_db(char_info, "en", self.user, is_guild_member=False)
        
        db_warning = ""
        if not (db_success_ko and db_success_en):
            db_warning = "\n⚠️ 데이터베이스 저장 중 일부 오류가 발생했습니다."
        
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

    async def update_discord_info_in_db(self, character_name: str, realm: str, user: discord.Member) -> bool:
        """DB에서 해당 캐릭터 행의 디스코드 정보를 업데이트"""
        try:
            database_url = os.getenv("DATABASE_URL")
            conn = await asyncpg.connect(database_url)
            
            discord_id = str(user.id)
            discord_username = user.name
            
            print(f">>> DB 디스코드 정보 업데이트: {character_name}-{realm} -> {discord_username}#{discord_id}")
            
            # 한국어, 영어 버전 모두 업데이트
            await conn.execute("""
                UPDATE guild_bot.guild_members 
                SET discord_id = $1, 
                    discord_username = $2,
                    updated_at = NOW()
                WHERE character_name = $3 AND realm = $4
            """, discord_id, discord_username, character_name, realm)
            
            await conn.close()
            print(f">>> DB 디스코드 정보 업데이트 성공")
            return True
            
        except Exception as e:
            print(f">>> DB 디스코드 정보 업데이트 오류: {e}")
            return False

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
            # DB에서 서버 정보 조회
            print(">>> DB에서 서버 정보 조회 시도")
            try:
                database_url = os.getenv("DATABASE_URL")
                if not database_url:
                    await interaction.followup.send("❌ 데이터베이스 연결 설정이 없어요!", ephemeral=True)
                    return
                
                conn = await asyncpg.connect(database_url)
                
                # 캐릭터명으로 DB에서 검색 (길드 멤버만)
                rows = await conn.fetch("""
                    SELECT DISTINCT character_name, realm, language 
                    FROM guild_bot.guild_members 
                    WHERE character_name = $1 AND is_guild_member = TRUE AND language = 'ko'
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
                    realm = row['realm']
                    print(f">>> 단일 서버 발견: {new_nickname}-{realm}")
                    
                    success = await self.update_discord_info_in_db(new_nickname, realm, interaction.user)
                    
                    if success:
                        new_nickname_with_emoji = f"🚀{new_nickname}"
                        try:
                            await interaction.user.edit(nick=new_nickname_with_emoji)
                            await interaction.followup.send(
                                f"✅ 닉네임이 **{new_nickname_with_emoji}**로 변경되었어요!\n"
                                f"🎮 서버: {realm}",
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
                            "⚠️ 데이터베이스 업데이트 중 오류가 발생했어요!",
                            ephemeral=True
                        )
                        
                else:
                    # 서버가 여러 개인 경우
                    print(f">>> 다중 서버 발견: {len(rows)}개")
                    server_options = []
                    for row in rows:
                        realm = row['realm']
                        server_options.append(discord.SelectOption(
                            label=f"{new_nickname}-{realm}",
                            value=realm,
                            description=f"{realm} 서버"
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

    @app_commands.command(name="일정", description="예정된 길드 이벤트를 보여줘요!")
    @guild_only() 
    async def show_events(self, interaction: Interaction):
        await interaction.response.defer()

        guild = interaction.guild
        events = await guild.fetch_scheduled_events()
        upcoming = [e for e in events if e.start_time and e.start_time > discord.utils.utcnow()]

        if not upcoming:
            await interaction.followup.send("다가오는 이벤트가 없어요! 💤")
            return

        import pytz
        from datetime import timedelta
        kst = pytz.timezone('Asia/Seoul')
        
        # 현재 한국 시간
        now_kst = discord.utils.utcnow().astimezone(kst)
        today = now_kst.date()
        
        # 다음 목요일 찾기
        current_weekday = today.weekday()  # 월요일=0, 목요일=3
        if current_weekday < 3:  # 월,화,수
            days_until_thursday = 3 - current_weekday
        else:  # 목,금,토,일
            days_until_thursday = 7 - (current_weekday - 3)
        
        next_thursday = today + timedelta(days=days_until_thursday)
        
        # 다음 목요일까지의 일정 필터링
        filtered_events = []
        for event in upcoming:
            event_date = event.start_time.astimezone(kst).date()
            if event_date <= next_thursday:
                filtered_events.sort(key=lambda e: e.start_time)
        filtered_events = filtered_events[:4]

        # 상대 날짜 계산 함수
        def get_relative_date(event_date, today):
            diff = (event_date - today).days
            if diff == 0:
                return "오늘"
            elif diff == 1:
                return "내일"
            elif diff == 2:
                return "모레"
            else:
                return f"{diff}일 후"

        # 메시지 구성
        msg = f"**📅 다가오는 목요일 전까지 일정**\n\n"
        
        if filtered_events:
            for i, event in enumerate(filtered_events):
                dt = event.start_time.astimezone(kst)
                event_date = dt.date()
                
                # 상대 날짜와 시간
                relative_date = get_relative_date(event_date, today)
                time_str = dt.strftime("%H:%M")
                
                # 요일 계산 수정 (월요일=0이므로 그대로 사용)
                weekdays = ['월', '화', '수', '목', '금', '토', '일']
                weekday = weekdays[event_date.weekday()]
                
                msg += f"{i+1}. **{relative_date} ({weekday}) {time_str}** - {event.name}\n"
        else:
            msg += "예정된 일정이 없어요! 💤"

        view = ui.View()

        # 레이드 채팅방 버튼 (꾸미기)
        raid_button = ui.Button(
            label="⚔️ 레이드 채팅방 입장", 
            style=discord.ButtonStyle.primary,  # 파란색
            emoji="🎮",
            url="https://discord.com/channels/1275099769731022971/1345938832658534511"
        )
        view.add_item(raid_button)

        await interaction.followup.send(msg, view=view)


    @app_commands.command(name="길드레이드", description="우리 길드의 레이드 진행도 또는 랭킹을 보여줘요!")
    @app_commands.describe(정보종류="진행도 또는 랭킹을 선택해주세요")
    @app_commands.choices(정보종류=[
        app_commands.Choice(name="진행도", value="raid_progression"),
        app_commands.Choice(name="랭킹", value="raid_rankings")
    ])
    async def guild_raid_info(self, interaction: Interaction, 정보종류: app_commands.Choice[str]):
        await interaction.response.defer()

        field = 정보종류.value
        guild_name_encoded = "우당탕탕 스톰윈드 지구대".replace(" ", "%20")
        url = (
            f"https://raider.io/api/v1/guilds/profile"
            f"?region=kr&realm=hyjal&name={guild_name_encoded}&fields={field}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(f"❌ 정보를 불러오지 못했어요 (상태 코드: {resp.status})")
                    return

                data = await resp.json()

                if field == "raid_progression":
                    raid = data.get("raid_progression", {}).get("manaforge-omega")
                    if not raid:
                        await interaction.followup.send("진행도 정보를 찾을 수 없어요 😢")
                        return

                    summary = raid.get("summary", "알 수 없음")
                    normal = raid.get("normal_bosses_killed", 0)
                    heroic = raid.get("heroic_bosses_killed", 0)
                    mythic = raid.get("mythic_bosses_killed", 0)

                    msg = (
                        f"💥 **마나 괴철로 종극점 레이드 진행도**\n"
                        f"📌 요약: {summary}\n"
                        f"> 일반 처치: {normal}넴\n"
                        f"> 영웅 처치: {heroic}넴\n"
                        f"> 신화 처치: {mythic}넴"
                    )
                    await interaction.followup.send(msg)

                elif field == "raid_rankings":
                    raid = data.get("raid_rankings", {}).get("manaforge-omega")
                    if not raid:
                        await interaction.followup.send("랭킹 정보를 찾을 수 없어요 😢")
                        return

                    def format_rank(rank):
                        return "없음" if rank == 0 else f"{rank:,}위"

                    msg = (
                        f"🏆 **마나 괴철로 종극점 레이드 랭킹**\n"
                        f"✅ **영웅 난이도**\n"
                        f"- 세계: {format_rank(raid['heroic']['world'])}\n"
                        f"- 아시아: {format_rank(raid['heroic']['region'])}\n"
                        f"- 하이잘: {format_rank(raid['heroic']['realm'])}\n\n"
                        f"💀 **신화 난이도**\n"
                        f"- 세계: {format_rank(raid['mythic']['world'])}\n"
                        f"- 아시아: {format_rank(raid['mythic']['region'])}\n"
                        f"- 하이잘: {format_rank(raid['mythic']['realm'])}"
                    )
                    await interaction.followup.send(msg)



# Cog 등록
async def setup(bot):
    await bot.add_cog(Raid(bot))