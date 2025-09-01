import asyncio
import asyncpg
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        
    async def create_pool(self):
        """데이터베이스 연결 풀 생성"""
        try:
            # DATABASE_URL 우선 사용 (현재 이게 성공함)
            database_url = os.getenv("DATABASE_URL")
            if database_url:
                self.pool = await asyncpg.create_pool(
                    database_url,
                    min_size=1,
                    max_size=10
                )
                print(">>> DATABASE_URL로 연결 풀 생성 완료!")
            else:
                # 개별 파라미터 방식 (fallback)
                self.pool = await asyncpg.create_pool(
                    host=os.getenv("DB_HOST", "localhost"),
                    port=int(os.getenv("DB_PORT", 5432)),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD"),
                    database=os.getenv("DB_NAME", "wow_guild_bot"),
                    min_size=1,
                    max_size=10
                )
                print(">>> 개별 파라미터로 연결 풀 생성 완료!")
                
        except Exception as e:
            print(f">>> 데이터베이스 연결 실패: {e}")
            raise

    async def close_pool(self):
        """연결 풀 종료"""
        if self.pool:
            await self.pool.close()
            print(">>> 데이터베이스 연결 종료")

    async def execute_query(self, query: str, *args) -> str:
        """쿼리 실행 (INSERT, UPDATE, DELETE)"""
        if not self.pool:
            print(">>> 데이터베이스 연결 풀이 없음")
            return None
            
        async with self.pool.acquire() as conn:
            try:
                result = await conn.execute(query, *args)
                print(f">>> 쿼리 실행 완료: {query[:50]}...")
                return result
            except Exception as e:
                print(f">>> 쿼리 실행 오류: {e}")
                raise

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """단일 행 조회"""
        if not self.pool:
            print(">>> 데이터베이스 연결 풀이 없음")
            return None
            
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(query, *args)
                print(f">>> 단일 행 조회: {query[:50]}... - 결과: {'있음' if row else '없음'}")
                return dict(row) if row else None
            except Exception as e:
                print(f">>> 단일 행 조회 오류: {e}")
                raise

    async def fetch_all(self, query: str, *args) -> List[Dict[str, Any]]:
        """여러 행 조회"""
        if not self.pool:
            print(">>> 데이터베이스 연결 풀이 없음")
            return []
            
        async with self.pool.acquire() as conn:
            try:
                rows = await conn.fetch(query, *args)
                print(f">>> 여러 행 조회: {query[:50]}... - 결과: {len(rows)}개")
                return [dict(row) for row in rows]
            except Exception as e:
                print(f">>> 여러 행 조회 오류: {e}")
                raise

    # 🎯 사용자 관련 메서드
    async def get_or_create_user(self, discord_id: str, display_name: str) -> Dict[str, Any]:
        """사용자 조회 또는 생성"""
        try:
            print(f">>> 사용자 조회/생성: {discord_id} - {display_name}")
            
            # 기존 사용자 확인
            user = await self.fetch_one(
                "SELECT * FROM users WHERE discord_id = $1", 
                discord_id
            )
            
            if user:
                # 디스플레이명 업데이트
                await self.execute_query(
                    "UPDATE users SET display_name = $1, last_seen = CURRENT_TIMESTAMP WHERE discord_id = $2",
                    display_name, discord_id
                )
                user['display_name'] = display_name
                print(f">>> 기존 사용자 업데이트: {discord_id}")
                return user
            else:
                # 새 사용자 생성
                await self.execute_query(
                    "INSERT INTO users (discord_id, display_name) VALUES ($1, $2)",
                    discord_id, display_name
                )
                print(f">>> 새 사용자 생성: {discord_id}")
                return await self.fetch_one(
                    "SELECT * FROM users WHERE discord_id = $1", 
                    discord_id
                )
        except Exception as e:
            print(f">>> 사용자 조회/생성 오류: {e}")
            raise

    # 🎯 캐릭터 관련 메서드
    async def set_character(self, discord_id: str, character_name: str, 
                           realm_slug: str, character_class: str = None,
                           character_spec: str = None, character_role: str = None) -> bool:
        """사용자의 메인 캐릭터 설정"""
        try:
            print(f">>> 캐릭터 설정: {discord_id} - {character_name}@{realm_slug}")
            
            # 기존 캐릭터 정보를 히스토리에 저장
            existing = await self.fetch_one(
                "SELECT * FROM characters WHERE discord_id = $1", 
                discord_id
            )
            
            if existing:
                await self.execute_query(
                    """INSERT INTO character_history 
                       (discord_id, character_name, realm_slug, character_class, character_spec, character_role)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    discord_id, existing['character_name'], existing['realm_slug'],
                    existing['character_class'], existing['character_spec'], existing['character_role']
                )
                print(f">>> 기존 캐릭터 히스토리 저장: {existing['character_name']}")
            
            # 새 캐릭터 정보 저장
            await self.execute_query(
                """INSERT INTO characters 
                   (discord_id, character_name, realm_slug, character_class, character_spec, character_role)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT (discord_id) 
                   DO UPDATE SET 
                       character_name = $2, realm_slug = $3, character_class = $4,
                       character_spec = $5, character_role = $6, updated_at = CURRENT_TIMESTAMP""",
                discord_id, character_name, realm_slug, character_class, character_spec, character_role
            )
            print(f">>> 캐릭터 설정 완료: {character_name}")
            return True
        except Exception as e:
            print(f">>> 캐릭터 설정 오류: {e}")
            return False

    async def get_user_character(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """사용자의 메인 캐릭터 조회"""
        try:
            character = await self.fetch_one(
                "SELECT * FROM characters WHERE discord_id = $1", 
                discord_id
            )
            print(f">>> 캐릭터 조회: {discord_id} - {'있음' if character else '없음'}")
            return character
        except Exception as e:
            print(f">>> 캐릭터 조회 오류: {e}")
            return None

    # 🎯 이벤트 관련 메서드
    async def create_event(self, event_name: str, title: str, description: str,
                          creator_discord_id: str, event_date: str = None, 
                          start_time: str = None, max_participants: int = 20) -> int:
        """이벤트 생성"""
        try:
            print(f">>> 이벤트 생성: {title} by {creator_discord_id}")
            
            # 중복 이벤트 확인 (같은 생성자가 5분 이내에 같은 제목으로 생성하는 것 방지)
            recent_event = await self.fetch_one(
                """SELECT id FROM events 
                   WHERE creator_discord_id = $1 AND title = $2 
                   AND created_at > NOW() - INTERVAL '5 minutes'
                   ORDER BY created_at DESC LIMIT 1""",
                creator_discord_id, title
            )
            
            if recent_event:
                print(f">>> 중복 이벤트 발견: {recent_event['id']}")
                return recent_event['id']
            
            result = await self.fetch_one(
                """INSERT INTO events 
                   (event_name, title, description, creator_discord_id, event_date, start_time, max_participants)
                   VALUES ($1, $2, $3, $4, $5, $6, $7) 
                   RETURNING id""",
                event_name, title, description, creator_discord_id, event_date, start_time, max_participants
            )
            event_id = result['id']
            print(f">>> 이벤트 생성 완료: ID {event_id}")
            return event_id
        except Exception as e:
            print(f">>> 이벤트 생성 오류: {e}")
            raise

    async def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """이벤트 조회"""
        try:
            event = await self.fetch_one(
                "SELECT * FROM events WHERE id = $1", 
                event_id
            )
            print(f">>> 이벤트 조회: ID {event_id} - {'있음' if event else '없음'}")
            return event
        except Exception as e:
            print(f">>> 이벤트 조회 오류: {e}")
            return None

    async def get_event_signups(self, event_id: int) -> List[Dict[str, Any]]:
        """이벤트 신청자 목록"""
        try:
            signups = await self.fetch_all(
                """SELECT es.*, u.display_name 
                   FROM event_signups es
                   JOIN users u ON es.discord_id = u.discord_id
                   WHERE es.event_id = $1 
                   ORDER BY es.signed_up_at""",
                event_id
            )
            print(f">>> 이벤트 신청자 조회: ID {event_id} - {len(signups)}명")
            return signups
        except Exception as e:
            print(f">>> 이벤트 신청자 조회 오류: {e}")
            return []

    async def signup_event(self, event_id: int, discord_id: str) -> bool:
        """이벤트 신청"""
        try:
            print(f">>> 이벤트 신청: ID {event_id} by {discord_id}")
            
            # 사용자의 메인 캐릭터 정보 가져오기
            character = await self.get_user_character(discord_id)
            if not character:
                print(f">>> 캐릭터 정보 없음: {discord_id}")
                return False

            # 이벤트 신청
            await self.execute_query(
                """INSERT INTO event_signups 
                   (event_id, discord_id, character_name, realm_slug, character_class, character_spec, character_role)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (event_id, discord_id) DO NOTHING""",
                event_id, discord_id, character['character_name'], character['realm_slug'],
                character['character_class'], character['character_spec'], character['character_role']
            )

            # 신청 히스토리에 기록
            await self.execute_query(
                """INSERT INTO event_signup_history 
                   (event_id, discord_id, action, character_name, realm_slug, character_class, character_spec, character_role)
                   VALUES ($1, $2, 'signup', $3, $4, $5, $6, $7)""",
                event_id, discord_id, character['character_name'], character['realm_slug'],
                character['character_class'], character['character_spec'], character['character_role']
            )
            
            print(f">>> 이벤트 신청 완료: {character['character_name']}")
            return True
        except Exception as e:
            print(f">>> 이벤트 신청 오류: {e}")
            return False

    async def cancel_signup(self, event_id: int, discord_id: str) -> bool:
        """이벤트 신청 취소"""
        try:
            print(f">>> 이벤트 신청 취소: ID {event_id} by {discord_id}")
            
            # 기존 신청 정보 가져오기
            signup = await self.fetch_one(
                "SELECT * FROM event_signups WHERE event_id = $1 AND discord_id = $2",
                event_id, discord_id
            )
            
            if not signup:
                print(f">>> 신청 정보 없음: {discord_id}")
                return False

            # 신청 취소
            await self.execute_query(
                "DELETE FROM event_signups WHERE event_id = $1 AND discord_id = $2",
                event_id, discord_id
            )

            # 취소 히스토리 기록
            await self.execute_query(
                """INSERT INTO event_signup_history 
                   (event_id, discord_id, action, character_name, realm_slug, character_class, character_spec, character_role)
                   VALUES ($1, $2, 'cancel', $3, $4, $5, $6, $7)""",
                event_id, discord_id, signup['character_name'], signup['realm_slug'],
                signup['character_class'], signup['character_spec'], signup['character_role']
            )
            
            print(f">>> 이벤트 신청 취소 완료: {signup['character_name']}")
            return True
        except Exception as e:
            print(f">>> 신청 취소 오류: {e}")
            return False

# 글로벌 데이터베이스 매니저 인스턴스
db = DatabaseManager()

# 테스트 함수
async def test_connection():
    """데이터베이스 연결 테스트"""
    try:
        await db.create_pool()
        
        # 테스트 쿼리
        result = await db.fetch_one("SELECT NOW() as current_time")
        print(f">>> 현재 시간: {result['current_time']}")
        
        # 테이블 확인
        tables = await db.fetch_all("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f">>> 생성된 테이블: {len(tables)}개")
        for table in tables:
            print(f"   - {table['table_name']}")
        
        await db.close_pool()
        print(">>> 데이터베이스 연결 테스트 성공!")
        
    except Exception as e:
        print(f">>> 데이터베이스 연결 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())