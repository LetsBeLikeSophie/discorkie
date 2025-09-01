import asyncio
import aiohttp
import asyncpg
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

TRANSLATIONS = {
    # ...existing translations dictionary...
    "race": {
        "Human": "인간", "Orc": "오크", "Dwarf": "드워프", "Night Elf": "나이트 엘프",
        "Undead": "언데드", "Tauren": "타우렌", "Gnome": "노움", "Troll": "트롤",
        "Goblin": "고블린", "Blood Elf": "블러드 엘프", "Draenei": "드라에나이",
        "Worgen": "늑대인간", "Pandaren": "판다렌", "Nightborne": "나이트본",
        "Highmountain Tauren": "높은산 타우렌", "Void Elf": "공허 엘프",
        "Lightforged Draenei": "빛벼림 드라에나이", "Zandalari Troll": "잔달라 트롤",
        "Kul Tiran": "쿨 티란", "Dark Iron Dwarf": "검은무쇠 드워프",
        "Vulpera": "불페라", "Mag'har Orc": "마그하르 오크", "Mechagnome": "메카노움",
        "Dracthyr": "드랙티르"
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
        "DPS": "딜",
        "TANK": "탱",
        "HEALING": "힐"
    }
    ,
    "realm": {
        "hyjal": "하이잘", "azshara": "아즈샤라", "durotan": "듀로탄",
        "zuljin": "줄진", "windrunner": "윈드러너", "wildhammer": "와일드해머",
        "rexxar": "렉사르", "guldan": "굴단", "deathwing": "데스윙",
        "burning legion": "불타는군단", "stormrage": "스톰레이지", "cenarius": "세나리우스",
        "malfurion": "말퓨리온", "hellscream": "헬스크림", "dalaran": "달라란",
        "garona": "가로나", "alexstrasza": "알렉스트라자"
    }
}


def safe_lower(value):
    return value.lower() if isinstance(value, str) else None


class GuildDataCollector:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def create_pool(self):
        try:
            database_url = os.getenv("DATABASE_URL")
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=10
            )
            print(">>> 데이터베이스 연결 풀 생성 완료")
        except Exception as e:
            print(f">>> 데이터베이스 연결 실패: {e}")
            raise
    
    async def close_pool(self):
        if self.pool:
            await self.pool.close()
    
    async def fetch_guild_members(self) -> List[Dict]:
        url = "https://raider.io/api/v1/guilds/profile"
        params = {
            "region": "kr",
            "realm": "hyjal", 
            "name": "우당탕탕 스톰윈드 지구대",
            "fields": "members"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get("members", [])
                        print(f">>> 길드 멤버 {len(members)}명 조회 완료")
                        return members
                    else:
                        print(f">>> API 호출 실패: {resp.status}")
                        return []
        except Exception as e:
            print(f">>> API 호출 오류: {e}")
            return []
    
    def translate_to_korean(self, category: str, english_value: str) -> str:
        if category in TRANSLATIONS:
            return TRANSLATIONS[category].get(english_value, english_value)
        return english_value
    
    async def insert_member_data(self, member: Dict, language: str):
        if not self.pool:
            print(">>> 데이터베이스 연결 없음")
            return False
        
        try:
            name = member.get("name")
            realm = member.get("realm").lower()
            if not name or not realm:
                print(f">>> 필수 데이터 누락: name={name}, realm={realm}")
                return False
            
            if language == "ko":
                race = self.translate_to_korean("race", member.get("race", ""))
                class_name = self.translate_to_korean("class", member.get("class", ""))
                active_spec = self.translate_to_korean("spec", member.get("active_spec_name", ""))
                active_spec_role = self.translate_to_korean("role", member.get("active_spec_role", ""))
                gender = self.translate_to_korean("gender", member.get("gender", ""))
                faction = self.translate_to_korean("faction", member.get("faction", ""))
                realm_display = self.translate_to_korean("realm", realm)
            else:
                race = member.get("race", "")
                class_name = member.get("class", "").lower()
                active_spec = safe_lower(member.get("active_spec_name"))
                active_spec_role = safe_lower(member.get("active_spec_role"))
                gender = member.get("gender", "").lower()
                faction = member.get("faction", "")
                realm_display = realm
            
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    INSERT INTO guild_members
                    (character_name, realm, is_guild_member,
                    language, race, class, active_spec, active_spec_role,
                    gender, faction, achievement_points,
                    profile_url, profile_banner, region, last_crawled_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                            $9, $10, $11, $12, $13, $14, NOW())
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
                        last_crawled_at = NOW(),
                        updated_at = NOW()
                """,
                name,
                realm_display,
                True,
                language,
                race,
                class_name,
                active_spec,
                active_spec_role,
                gender,
                faction,
                member.get("achievement_points", 0),
                member.get("profile_url", ""),
                member.get("profile_banner", ""),
                "kr"
                )
                print(f"    DB 실행 결과: {result}")
                return True
        except Exception as e:
            print(f">>> {name} 데이터 삽입 오류: {e}")
            return False
    
    async def get_guild_member_count(self, language: str = None) -> int:
        if not self.pool:
            return 0
        try:
            async with self.pool.acquire() as conn:
                if language:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM guild_members WHERE is_guild_member = TRUE AND language = $1",
                        language
                    )
                else:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM guild_members WHERE is_guild_member = TRUE"
                    )
                return result or 0
        except Exception as e:
            print(f">>> 레코드 수 조회 오류: {e}")
            return 0

    async def collect_guild_data(self):
        print(">>> 길드 데이터 수집 시작")
        before_count = await self.get_guild_member_count()
        print(f">>> 처리 전 DB 레코드 수: {before_count}개")
        members = await self.fetch_guild_members()
        if not members:
            print(">>> 길드 멤버 데이터 없음")
            return
        if members:
            print(f">>> 첫 번째 멤버 샘플 데이터:")
            first_member = members[0]
            for key, value in first_member.items():
                print(f"    {key}: {value}")
        for i, member in enumerate(members, 1):  # 모든 멤버 처리
            # character와 member를 합쳐서 평평한 구조로 만듦
            character = member.get("character", {})
            full_data = {**character, **member}
            name = full_data.get("name", "Unknown")
            print(f"\n>>> [{i}/{len(members)}] {name} 처리 중...")
            print(f"    영문 데이터 삽입...")
            en_success = await self.insert_member_data(full_data, "en")
            print(f"    한글 데이터 삽입...")
            ko_success = await self.insert_member_data(full_data, "ko")
        after_count = await self.get_guild_member_count()
        korean_records = await self.get_guild_member_count(language="ko")
        english_records = await self.get_guild_member_count(language="en")
        print(f"\n>>> 길드 데이터 처리 결과:")
        print(f"    API에서 조회한 멤버 수: {len(members)}명")
        print(f"    처리 전 DB 레코드 수: {before_count}개")
        print(f"    처리 후 DB 레코드 수: {after_count}개")
        print(f"    한글 레코드 수: {korean_records}개")
        print(f"    영문 레코드 수: {english_records}개")
        print(f"    실제 추가된 레코드: {after_count - before_count}개")


    async def insert_from_api(self):
        await self.create_pool()
        try:
            members = await self.fetch_guild_members()
            if not members:
                print(">>> No members fetched from Raider.io API")
                return
            for i, member in enumerate(members, 1):  # 모든 멤버 처리
                character = member.get("character", {})
                name = character.get("name", "Unknown")
                realm = character.get("realm")
                print(f"\n>>> [{i}/{len(members)}] {name} 처리 중...")
                if not name or not realm:
                    print(f">>> 필수 데이터 누락: name={name}, realm={realm}")
                    continue
                full_data = {**character, **member}
                print("  영어 데이터 삽입 중...")
                await self.insert_member_data(full_data, "en")
                print("  한글 데이터 삽입 중...")
                await self.insert_member_data(full_data, "ko")
        finally:
            await self.close_pool()

# 실행 함수
async def main():
    collector = GuildDataCollector()
    try:
        await collector.create_pool()
        await collector.collect_guild_data()
    finally:
        await collector.close_pool()

if __name__ == "__main__":
    asyncio.run(main())