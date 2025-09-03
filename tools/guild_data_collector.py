import asyncio
import aiohttp
import asyncpg
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

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
    
    async def insert_member_data(self, member_data: Dict) -> bool:
        """멤버 데이터를 데이터베이스에 삽입 (raider.io API 응답 그대로 저장)"""
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
            
            # raider.io API 응답값 그대로 사용
            race = normalized_data.get("race", "")
            class_name = normalized_data.get("class", "")
            active_spec = normalized_data.get("active_spec_name", "")
            active_spec_role = normalized_data.get("active_spec_role", "")
            gender = normalized_data.get("gender", "")
            faction = normalized_data.get("faction", "")
            
            # 데이터베이스에 삽입 (language 컬럼 제거)
            async with self.pool.acquire() as conn:
                result = await conn.execute("""
                    INSERT INTO guild_bot.guild_members (
                        character_name, realm, is_guild_member,
                        race, class, active_spec, active_spec_role,
                        gender, faction, achievement_points,
                        profile_url, profile_banner, thumbnail_url, region, last_crawled_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7,
                            $8, $9, $10, $11, $12, $13, $14, NOW())
                    ON CONFLICT (character_name, realm)
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
                True,  # is_guild_member
                race,
                class_name,
                active_spec,
                active_spec_role,
                gender,
                faction,
                normalized_data.get("achievement_points", 0),
                normalized_data.get("profile_url", ""),
                normalized_data.get("profile_banner", ""),
                normalized_data.get("thumbnail_url", ""),
                "kr"  # region
                )
                
                print(f"    ✓ {name}-{realm} 데이터 삽입 완료")
                return True
                
        except Exception as e:
            name = normalized_data.get("name", "Unknown") if 'normalized_data' in locals() else member_data.get("name", "Unknown")
            print(f">>> ✗ {name} 데이터 삽입 오류: {e}")
            return False
    
    async def get_guild_member_count(self) -> int:
        """길드 멤버 수 조회"""
        if not self.pool:
            return 0
        
        try:
            async with self.pool.acquire() as conn:
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
        
        # 각 멤버 데이터 처리 (단일 행만 삽입)
        success_count = 0
        for i, member in enumerate(members, 1):
            name = member.get("character", {}).get("name", "Unknown")
            print(f"\n>>> [{i}/{len(members)}] {name} 처리 중...")
            
            # 단일 데이터 삽입 (언어별 중복 제거)
            if await self.insert_member_data(member):
                success_count += 1
        
        # 처리 후 결과 출력
        after_count = await self.get_guild_member_count()
        
        print(f"\n>>> 길드 데이터 처리 결과:")
        print(f"    API에서 조회한 멤버 수: {len(members)}명")
        print(f"    처리 전 DB 레코드 수: {before_count}개")
        print(f"    처리 후 DB 레코드 수: {after_count}개")
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