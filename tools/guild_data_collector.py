import asyncio
import aiohttp
import asyncpg
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

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
    # 소문자 줄'진, 굴'단이랑 불타는 군단 확인
    # "realm": {
    #     "hyjal": "하이잘", "azshara": "아즈샤라", "durotan": "듀로탄",
    #     "zuljin": "줄진", "windrunner": "윈드러너", "wildhammer": "와일드해머",
    #     "rexxar": "렉사르", "guldan": "굴단", "deathwing": "데스윙",
    #     "burning legion": "불타는군단", "stormrage": "스톰레이지", "cenarius": "세나리우스",
    #     "malfurion": "말퓨리온", "hellscream": "헬스크림", "dalaran": "달라란",
    #     "garona": "가로나", "alexstrasza": "알렉스트라자"
    # }



def safe_lower(value):
    """안전하게 소문자로 변환"""
    return value.lower() if isinstance(value, str) else None


class GuildDataCollector:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def create_pool(self):
        """데이터베이스 연결 풀 생성"""
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
        """데이터베이스 연결 풀 종료"""
        if self.pool:
            await self.pool.close()
    
    async def fetch_guild_members(self) -> List[Dict]:
        """Raider.io API에서 길드 멤버 정보 가져오기"""
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
                        
                        # 첫 번째 멤버의 데이터 구조 출력 (디버깅용)
                        if members:
                            print(">>> 첫 번째 멤버 데이터 구조:")
                            first_member = members[0]
                            print(f"    루트 레벨 키들: {list(first_member.keys())}")
                            if 'character' in first_member:
                                print(f"    character 키들: {list(first_member['character'].keys())}")
                        
                        return members
                    else:
                        print(f">>> API 호출 실패: {resp.status}")
                        return []
        except Exception as e:
            print(f">>> API 호출 오류: {e}")
            return []
    
    def normalize_member_data(self, member_data: Dict) -> Dict:
        """멤버 데이터를 정규화하여 평평한 구조로 변환"""
        # character 내부의 데이터를 루트 레벨로 올리기
        character_data = member_data.get("character", {})
        
        # 루트 레벨의 데이터와 character 데이터 병합
        # 루트 레벨 데이터가 우선순위를 가짐 (thumbnail_url 등)
        normalized = {**character_data, **member_data}
        
        # character 키는 제거 (이미 병합했으므로)
        normalized.pop("character", None)
        
        return normalized
    
    def translate_to_korean(self, category: str, english_value: str) -> str:
        """영문 값을 한국어로 번역"""
        if category in TRANSLATIONS:
            return TRANSLATIONS[category].get(english_value, english_value)
        return english_value
    
    async def insert_member_data(self, member_data: Dict, language: str):
        """멤버 데이터를 데이터베이스에 삽입"""
        if not self.pool:
            print(">>> 데이터베이스 연결 없음")
            return False
        
        try:
            # 데이터 정규화
            normalized_data = self.normalize_member_data(member_data)
            
            name = normalized_data.get("name")
            realm = normalized_data.get("realm")
            
            if not name or not realm:
                print(f">>> 필수 데이터 누락: name={name}, realm={realm}")
                return False
            
            # # realm을 소문자로 정규화
            # realm = realm.lower() if isinstance(realm, str) else ""
            
            # 언어에 따른 데이터 변환
            if language == "ko":
                race = self.translate_to_korean("race", normalized_data.get("race", ""))
                class_name = self.translate_to_korean("class", normalized_data.get("class", ""))
                active_spec = self.translate_to_korean("spec", normalized_data.get("active_spec_name", ""))
                active_spec_role = self.translate_to_korean("role", normalized_data.get("active_spec_role", ""))
                gender = self.translate_to_korean("gender", normalized_data.get("gender", ""))
                faction = self.translate_to_korean("faction", normalized_data.get("faction", ""))
                realm_display = self.translate_to_korean("realm", realm)
            else:
                race = normalized_data.get("race", "")
                class_name = safe_lower(normalized_data.get("class", ""))
                active_spec = safe_lower(normalized_data.get("active_spec_name", ""))
                active_spec_role = safe_lower(normalized_data.get("active_spec_role", ""))
                gender = safe_lower(normalized_data.get("gender", ""))
                faction = normalized_data.get("faction", "")
                realm_display = realm

            # 데이터베이스에 삽입
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    INSERT INTO guild_bot.guild_members (
                        character_name, realm, is_guild_member,
                        language, race, class, active_spec, active_spec_role,
                        gender, faction, achievement_points,
                        profile_url, profile_banner, thumbnail_url, region, last_crawled_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                            $9, $10, $11, $12, $13, $14, $15, NOW())
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
                        updated_at = NOW()
                """,
                name,
                realm_display,
                True,  # is_guild_member
                language,
                race,
                class_name,
                active_spec,
                active_spec_role,
                gender,
                faction,
                normalized_data.get("achievement_points", 0),
                normalized_data.get("profile_url", ""),
                normalized_data.get("profile_banner", ""),
                normalized_data.get("thumbnail_url", ""),  # 이제 정확히 가져와짐
                "kr"  # region
                )
                
                print(f"    ✓ {name} ({language}) 데이터 삽입 완료")
                return True
                
        except Exception as e:
            name = member_data.get("name", "Unknown")
            print(f">>> ✗ {name} ({language}) 데이터 삽입 오류: {e}")
            return False
    
    async def get_guild_member_count(self, language: str = None) -> int:
        """길드 멤버 수 조회"""
        if not self.pool:
            return 0
        
        try:
            async with self.pool.acquire() as conn:
                if language:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM guild_bot.guild_members WHERE is_guild_member = TRUE AND language = $1",
                        language
                    )
                else:
                    result = await conn.fetchval(
                        "SELECT COUNT(*) FROM guild_bot.guild_members WHERE is_guild_member = TRUE"
                    )
                return result or 0
        except Exception as e:
            print(f">>> 레코드 수 조회 오류: {e}")
            return 0

    async def collect_guild_data(self):
        """길드 데이터 수집 메인 함수"""
        print(">>> 길드 데이터 수집 시작")
        
        # 처리 전 상태 확인
        before_count = await self.get_guild_member_count()
        print(f">>> 처리 전 DB 레코드 수: {before_count}개")
        
        # API에서 멤버 데이터 가져오기
        members = await self.fetch_guild_members()
        if not members:
            print(">>> 길드 멤버 데이터 없음")
            return
        
        # 각 멤버 데이터 처리
        success_count = 0
        for i, member in enumerate(members, 1):
            name = member.get("character", {}).get("name", "Unknown")
            print(f"\n>>> [{i}/{len(members)}] {name} 처리 중...")
            
            # 영문 데이터 삽입
            if await self.insert_member_data(member, "en"):
                success_count += 1
            
            # 한글 데이터 삽입
            if await self.insert_member_data(member, "ko"):
                success_count += 1
        
        # 처리 후 결과 출력
        after_count = await self.get_guild_member_count()
        korean_records = await self.get_guild_member_count(language="ko")
        english_records = await self.get_guild_member_count(language="en")
        
        print(f"\n>>> 길드 데이터 처리 결과:")
        print(f"    API에서 조회한 멤버 수: {len(members)}명")
        print(f"    처리 전 DB 레코드 수: {before_count}개")
        print(f"    처리 후 DB 레코드 수: {after_count}개")
        print(f"    한글 레코드 수: {korean_records}개")
        print(f"    영문 레코드 수: {english_records}개")
        print(f"    성공적으로 처리된 작업: {success_count}개")

    async def insert_from_api(self):
        """API에서 데이터를 가져와 삽입하는 독립 실행 함수"""
        await self.create_pool()
        try:
            await self.collect_guild_data()
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