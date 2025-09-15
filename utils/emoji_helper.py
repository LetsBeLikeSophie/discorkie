"""
utils/emoji_helper.py

서버 이모티콘 데이터를 로딩하고 관리하는 헬퍼 함수들
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional

class EmojiManager:
    def __init__(self):
        self._emojis_data = None
        self._class_emojis = None
        self._role_emojis = None
        self._loaded = False
        
    def load_emojis(self) -> bool:
        """이모티콘 데이터 로딩"""
        if self._loaded:
            return True
            
        try:
            # data/server_emojis.json 파일 경로
            data_file = Path(__file__).parent.parent / 'data' / 'server_emojis.json'
            
            if not data_file.exists():
                print(f">>> 이모티콘 파일이 존재하지 않음: {data_file}")
                print(">>> tools/fetch_server_emojis.py를 먼저 실행해주세요")
                return False
            
            with open(data_file, 'r', encoding='utf-8') as f:
                self._emojis_data = json.load(f)
            
            # 직업별 이모티콘 매핑 생성
            self._class_emojis = {}
            if 'wow_classes' in self._emojis_data:
                for class_name, emoji_data in self._emojis_data['wow_classes'].items():
                    self._class_emojis[class_name.lower()] = emoji_data['format']
            
            # 역할별 이모티콘 매핑 생성 (기본값 포함)
            self._role_emojis = {
                'tank': '🛡️',
                'healer': '💚', 
                'dps': '⚔️',
                'damage': '⚔️'
            }
            
            # 서버 이모티콘으로 덮어쓰기 (있는 경우)
            if 'wow_roles' in self._emojis_data:
                for role_name, emoji_data in self._emojis_data['wow_roles'].items():
                    self._role_emojis[role_name.lower()] = emoji_data['format']
            
            self._loaded = True
            print(f">>> 이모티콘 데이터 로딩 완료: {len(self._class_emojis)}개 직업, {len(self._role_emojis)}개 역할")
            return True
            
        except Exception as e:
            print(f">>> 이모티콘 로딩 오류: {e}")
            return False
    
    def get_class_emoji(self, class_name: str) -> str:
        """직업 이모티콘 가져오기"""
        if not self._loaded:
            self.load_emojis()
        
        if not self._class_emojis:
            return "❓"  # 기본값
        
        # 다양한 형태의 직업명 처리
        class_key = class_name.lower().strip()
        
        # 직접 매칭
        if class_key in self._class_emojis:
            return self._class_emojis[class_key]
        
        # Death Knight -> deathknight 변환
        class_key = class_key.replace(' ', '').replace('_', '').replace('-', '')
        
        # 부분 매칭
        for key, emoji in self._class_emojis.items():
            if key.replace('_', '').replace('-', '') == class_key:
                return emoji
        
        print(f">>> 알 수 없는 직업: {class_name}")
        return "❓"  # 알 수 없는 직업
    
    def get_role_emoji(self, role_name: str) -> str:
        """역할 이모티콘 가져오기"""
        if not self._loaded:
            self.load_emojis()
        
        role_key = role_name.lower().strip()
        
        # 역할명 정규화
        role_mapping = {
            'tank': 'tank',
            'healer': 'healer',
            'heal': 'healer',
            'healing': 'healer',
            'dps': 'dps',
            'damage': 'dps',
            'dd': 'dps',
            'melee': 'dps',
            'ranged': 'dps'
        }
        
        normalized_role = role_mapping.get(role_key, role_key)
        
        if normalized_role in self._role_emojis:
            return self._role_emojis[normalized_role]
        
        print(f">>> 알 수 없는 역할: {role_name}")
        return "❓"  # 알 수 없는 역할
    
    def get_status_emoji(self, status: str) -> str:
        """참여 상태 이모티콘 가져오기"""
        status_emojis = {
            'confirmed': '✅',
            'tentative': '❓',
            'declined': '❌',
            'pending': '⏳'
        }
        
        return status_emojis.get(status.lower(), '❓')
    
    def get_all_class_emojis(self) -> Dict[str, str]:
        """모든 직업 이모티콘 딕셔너리 반환"""
        if not self._loaded:
            self.load_emojis()
        
        return self._class_emojis.copy() if self._class_emojis else {}
    
    def get_all_role_emojis(self) -> Dict[str, str]:
        """모든 역할 이모티콘 딕셔너리 반환"""
        if not self._loaded:
            self.load_emojis()
        
        return self._role_emojis.copy() if self._role_emojis else {}
    
    def is_loaded(self) -> bool:
        """로딩 상태 확인"""
        return self._loaded
    
    def get_emoji_info(self) -> Optional[Dict]:
        """이모티콘 데이터 정보 반환"""
        if not self._loaded:
            self.load_emojis()
        
        return self._emojis_data

# 전역 인스턴스
_emoji_manager = EmojiManager()

# 편의 함수들
def get_class_emoji(class_name: str) -> str:
    """직업 이모티콘 가져오기 (편의 함수)"""
    return _emoji_manager.get_class_emoji(class_name)

def get_role_emoji(role_name: str) -> str:
    """역할 이모티콘 가져오기 (편의 함수)"""
    return _emoji_manager.get_role_emoji(role_name)

def get_status_emoji(status: str) -> str:
    """상태 이모티콘 가져오기 (편의 함수)"""
    return _emoji_manager.get_status_emoji(status)

def load_emojis() -> bool:
    """이모티콘 로딩 (편의 함수)"""
    return _emoji_manager.load_emojis()

def is_emojis_loaded() -> bool:
    """로딩 상태 확인 (편의 함수)"""
    return _emoji_manager.is_loaded()

# 테스트 함수
def test_emojis():
    """이모티콘 테스트"""
    print(">>> 이모티콘 테스트 시작")
    
    if not load_emojis():
        print(">>> 이모티콘 로딩 실패")
        return
    
    # 직업 테스트
    test_classes = ['warrior', 'mage', 'priest', 'death_knight', 'demon_hunter']
    print("\n>>> 직업 이모티콘 테스트:")
    for class_name in test_classes:
        emoji = get_class_emoji(class_name)
        print(f">>>   {class_name}: {emoji}")
    
    # 역할 테스트
    test_roles = ['tank', 'healer', 'dps', 'damage']
    print("\n>>> 역할 이모티콘 테스트:")
    for role_name in test_roles:
        emoji = get_role_emoji(role_name)
        print(f">>>   {role_name}: {emoji}")
    
    # 상태 테스트
    test_statuses = ['confirmed', 'tentative', 'declined']
    print("\n>>> 상태 이모티콘 테스트:")
    for status in test_statuses:
        emoji = get_status_emoji(status)
        print(f">>>   {status}: {emoji}")

if __name__ == "__main__":
    test_emojis()