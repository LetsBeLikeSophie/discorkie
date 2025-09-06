import asyncpg
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = os.getenv("DATABASE_URL")
    
    async def create_pool(self):
        """데이터베이스 연결 풀 생성"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
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
            print(">>> 데이터베이스 연결 풀 종료")
    
    def get_connection(self):
        """연결 풀에서 연결 가져오기"""
        if not self.pool:
            raise Exception("데이터베이스 풀이 생성되지 않음")
        return self.pool.acquire()