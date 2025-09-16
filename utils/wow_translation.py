"""
utils/wow_translation.py

WoW 관련 용어들의 한국어-영어 번역을 관리하는 모듈
"""

# 서버명 번역 (한국어 -> 영어)
REALM_KR_TO_EN = {
    # 주요 서버들
    "가로나": "Garona",
    "아즈샤라": "Azshara", 
    "불타는군단": "Burning Legion",
    "세나리우스": "Cenarius",
    "굴단": "Gul'dan",
    "스톰레이지": "Stormrage",
    "알렉스트라자": "Alexstrasza",
    "줄진": "Zul'jin",
    "렉사르": "Rexxar",
    "하이잘": "Hyjal",
    "듀로탄": "Durotan",
    "달라란": "Dalaran",
    "헬스크림": "Hellscream",
    "데스윙": "Deathwing",
    
    # 추가 서버들 (필요시 확장)
    "와일드해머": "Wildhammer",
    "말퓨리온": "Malfurion",
    "노르간논": "Norgannon",
    "윈드러너": "Windrunner",
    "마법사의탑": "Magtheridon"
}

# 서버명 번역 (영어 -> 한국어)
REALM_EN_TO_KR = {v: k for k, v in REALM_KR_TO_EN.items()}

# 직업명 번역 (한국어 -> 영어)
CLASS_KR_TO_EN = {
    "전사": "Warrior",
    "성기사": "Paladin", 
    "사냥꾼": "Hunter",
    "도적": "Rogue",
    "사제": "Priest",
    "주술사": "Shaman",
    "마법사": "Mage",
    "흑마법사": "Warlock",
    "수도사": "Monk",
    "드루이드": "Druid",
    "악마사냥꾼": "Demon Hunter",
    "죽음의기사": "Death Knight",
    "기원사": "Evoker"
}

# 직업명 번역 (영어 -> 한국어)
CLASS_EN_TO_KR = {v: k for k, v in CLASS_KR_TO_EN.items()}

# 전문화 번역 (영어 -> 한국어)
SPEC_EN_TO_KR = {
    # 전사
    "Arms": "무기",
    "Fury": "분노", 
    "Protection": "방어",
    
    # 성기사
    "Holy": "신성",
    "Retribution": "징벌",
    "Protection": "보호",  
    
    # 사냥꾼
    "Beast Mastery": "야수",
    "Marksmanship": "사격",
    "Survival": "생존",
    
    # 도적
    "Assassination": "암살",
    "Outlaw": "무법",
    "Subtlety": "잠행",
    
    # 사제
    "Discipline": "수양",
    "Shadow": "암흑",
    
    # 주술사
    "Elemental": "정기",
    "Enhancement": "고양",
    "Restoration": "복원",
    
    # 마법사
    "Arcane": "비전",
    "Fire": "화염", 
    "Frost": "냉기",
    
    # 흑마법사
    "Affliction": "고통",
    "Demonology": "악마",
    "Destruction": "파괴",
    
    # 수도사
    "Brewmaster": "양조",
    "Mistweaver": "운무",
    "Windwalker": "풍운",
    
    # 드루이드
    "Balance": "조화",
    "Feral": "야성",
    "Guardian": "수호",
    "Restoration": "회복",
    
    # 악마사냥꾼
    "Havoc": "파멸",
    "Vengeance": "복수",
    
    # 죽음의기사
    "Blood": "혈기",
    "Unholy": "부정",
    
    # 용술사
    "Devastation": "황폐",
    "Preservation": "보존",
    "Augmentation": "증강"
}

# 전문화 번역 (한국어 -> 영어)
SPEC_KR_TO_EN = {v: k for k, v in SPEC_EN_TO_KR.items()}

# 역할 번역 (영어 -> 한국어)
ROLE_EN_TO_KR = {
    "Tank": "탱커",
    "Healer": "힐러",
    "DPS": "딜러",
    "Damage": "딜러",
    "Melee": "근딜",
    "Ranged": "원딜"
}

# 역할 번역 (한국어 -> 영어)
ROLE_KR_TO_EN = {v: k for k, v in ROLE_EN_TO_KR.items()}

class WoWTranslator:
    """WoW 용어 번역 클래스"""
    
    @staticmethod
    def realm_kr_to_en(korean_name: str) -> str:
        """한국어 서버명을 영어로 변환"""
        # 공백 제거 및 정규화
        normalized = korean_name.strip().replace(" ", "")
        
        # 직접 매칭
        if normalized in REALM_KR_TO_EN:
            return REALM_KR_TO_EN[normalized]
        
        # 부분 매칭 시도
        for kr_name, en_name in REALM_KR_TO_EN.items():
            if normalized in kr_name or kr_name in normalized:
                return en_name
        
        # 매칭 실패 시 원본 반환 (이미 영어일 수 있음)
        return korean_name
    
    @staticmethod
    def realm_en_to_kr(english_name: str) -> str:
        """영어 서버명을 한국어로 변환"""
        # Pascal Case 정규화
        normalized = english_name.strip().replace(" ", "").replace("'", "'")
        
        if normalized in REALM_EN_TO_KR:
            return REALM_EN_TO_KR[normalized]
        
        # 매칭 실패 시 원본 반환
        return english_name
    
    @staticmethod
    def class_en_to_kr(english_class: str) -> str:
        """영어 직업명을 한국어로 변환"""
        normalized = english_class.strip().title()
        
        if normalized in CLASS_EN_TO_KR:
            return CLASS_EN_TO_KR[normalized]
        
        return english_class
    
    @staticmethod
    def spec_en_to_kr(english_spec: str) -> str:
        """영어 전문화명을 한국어로 변환"""
        normalized = english_spec.strip().title()
        
        if normalized in SPEC_EN_TO_KR:
            return SPEC_EN_TO_KR[normalized]
        
        return english_spec
    
    @staticmethod
    def role_en_to_kr(english_role: str) -> str:
        """영어 역할명을 한국어로 변환"""
        normalized = english_role.strip().title()
        
        if normalized in ROLE_EN_TO_KR:
            return ROLE_EN_TO_KR[normalized]
        
        return english_role
    
    @staticmethod
    def get_realm_suggestions(partial_name: str) -> list:
        """부분 서버명으로 추천 목록 반환"""
        suggestions = []
        partial = partial_name.lower().strip()
        
        # 한국어 검색
        for kr_name, en_name in REALM_KR_TO_EN.items():
            if partial in kr_name.lower():
                suggestions.append(f"{kr_name} ({en_name})")
        
        # 영어 검색
        for en_name, kr_name in REALM_EN_TO_KR.items():
            if partial in en_name.lower():
                suggestion = f"{kr_name} ({en_name})"
                if suggestion not in suggestions:
                    suggestions.append(suggestion)
        
        return suggestions[:5]  # 최대 5개까지
    
    @staticmethod
    def normalize_user_input(user_input: str, input_type: str = "realm") -> str:
        """사용자 입력을 정규화하여 API 호출에 적합한 형태로 변환"""
        cleaned = user_input.strip()
        
        if input_type == "realm":
            # 한국어 서버명이면 영어로 변환
            return WoWTranslator.realm_kr_to_en(cleaned)
        elif input_type == "character":
            # 캐릭터명은 그대로 (특수문자만 정리)
            return cleaned
        
        return cleaned

# 편의 함수들
def translate_realm_kr_to_en(korean_name: str) -> str:
    """한국어 서버명 -> 영어 (편의 함수)"""
    return WoWTranslator.realm_kr_to_en(korean_name)

def translate_realm_en_to_kr(english_name: str) -> str:
    """영어 서버명 -> 한국어 (편의 함수)"""
    return WoWTranslator.realm_en_to_kr(english_name)

def translate_spec_en_to_kr(english_spec: str) -> str:
    """영어 전문화 -> 한국어 (편의 함수)"""
    return WoWTranslator.spec_en_to_kr(english_spec)

def translate_class_en_to_kr(english_class: str) -> str:
    """영어 직업 -> 한국어 (편의 함수)"""
    return WoWTranslator.class_en_to_kr(english_class)

def normalize_realm_input(user_input: str) -> str:
    """사용자 서버명 입력 정규화 (편의 함수)"""
    return WoWTranslator.normalize_user_input(user_input, "realm")

# 테스트 함수
def test_translation():
    """번역 기능 테스트"""
    print(">>> WoW 번역 테스트 시작")
    
    # 서버명 테스트
    test_realms = ["아즈샤라", "Azshara", "하이잘", "Hyjal", "불타는군단"]
    print("\n>>> 서버명 번역 테스트:")
    for realm in test_realms:
        kr_to_en = translate_realm_kr_to_en(realm)
        en_to_kr = translate_realm_en_to_kr(realm)
        print(f">>>   {realm} -> 영어: {kr_to_en}, 한국어: {en_to_kr}")
    
    # 전문화 테스트
    test_specs = ["Blood", "Holy", "Arcane", "Beast Mastery"]
    print("\n>>> 전문화 번역 테스트:")
    for spec in test_specs:
        kr_spec = translate_spec_en_to_kr(spec)
        print(f">>>   {spec} -> {kr_spec}")
    
    # 직업 테스트
    test_classes = ["Warrior", "Mage", "Death Knight", "Demon Hunter"]
    print("\n>>> 직업 번역 테스트:")
    for cls in test_classes:
        kr_cls = translate_class_en_to_kr(cls)
        print(f">>>   {cls} -> {kr_cls}")

if __name__ == "__main__":
    test_translation()