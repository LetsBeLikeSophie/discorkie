"""
utils/wow_role_mapping.py

WoW 직업과 전문화 조합에 따른 역할 매핑
TANK, HEALER, MELEE_DPS, RANGED_DPS로 세분화
"""

# 직업별 전문화 역할 매핑
CLASS_SPEC_ROLES = {
    # 전사 (Warrior)
    ("Warrior", "Arms"): "MELEE_DPS",
    ("Warrior", "Fury"): "MELEE_DPS", 
    ("Warrior", "Protection"): "TANK",
    
    # 성기사 (Paladin)
    ("Paladin", "Holy"): "HEALER",
    ("Paladin", "Protection"): "TANK",
    ("Paladin", "Retribution"): "MELEE_DPS",
    
    # 사냥꾼 (Hunter)
    ("Hunter", "Beast Mastery"): "RANGED_DPS",
    ("Hunter", "Marksmanship"): "RANGED_DPS",
    ("Hunter", "Survival"): "MELEE_DPS",  # 근접 DPS
    
    # 도적 (Rogue)
    ("Rogue", "Assassination"): "MELEE_DPS",
    ("Rogue", "Outlaw"): "MELEE_DPS",
    ("Rogue", "Subtlety"): "MELEE_DPS",
    
    # 사제 (Priest)
    ("Priest", "Discipline"): "HEALER",
    ("Priest", "Holy"): "HEALER",
    ("Priest", "Shadow"): "RANGED_DPS",
    
    # 주술사 (Shaman)
    ("Shaman", "Elemental"): "RANGED_DPS",
    ("Shaman", "Enhancement"): "MELEE_DPS",
    ("Shaman", "Restoration"): "HEALER",
    
    # 마법사 (Mage)
    ("Mage", "Arcane"): "RANGED_DPS",
    ("Mage", "Fire"): "RANGED_DPS",
    ("Mage", "Frost"): "RANGED_DPS",
    
    # 흑마법사 (Warlock)
    ("Warlock", "Affliction"): "RANGED_DPS",
    ("Warlock", "Demonology"): "RANGED_DPS",
    ("Warlock", "Destruction"): "RANGED_DPS",
    
    # 수도사 (Monk)
    ("Monk", "Brewmaster"): "TANK",
    ("Monk", "Mistweaver"): "HEALER",
    ("Monk", "Windwalker"): "MELEE_DPS",
    
    # 드루이드 (Druid)
    ("Druid", "Balance"): "RANGED_DPS",
    ("Druid", "Feral"): "MELEE_DPS",
    ("Druid", "Guardian"): "TANK",
    ("Druid", "Restoration"): "HEALER",
    
    # 악마사냥꾼 (Demon Hunter)
    ("Demon Hunter", "Havoc"): "MELEE_DPS",
    ("Demon Hunter", "Vengeance"): "TANK",
    
    # 죽음의 기사 (Death Knight)
    ("Death Knight", "Blood"): "TANK",
    ("Death Knight", "Frost"): "MELEE_DPS",
    ("Death Knight", "Unholy"): "MELEE_DPS",
    
    # 용술사 (Evoker)
    ("Evoker", "Devastation"): "RANGED_DPS",
    ("Evoker", "Preservation"): "HEALER",
    ("Evoker", "Augmentation"): "RANGED_DPS",  # 지원형 DPS지만 원거리로 분류
}

# 장비 소재 매핑 (방어구 타입)
CLASS_ARMOR_TYPE = {
    "Warrior": "판금",
    "Paladin": "판금",
    "Death Knight": "판금",
    
    "Hunter": "사슬",
    "Shaman": "사슬",
    "Evoker": "사슬",
    
    "Rogue": "가죽",
    "Monk": "가죽",
    "Druid": "가죽",
    "Demon Hunter": "가죽",
    
    "Priest": "천",
    "Mage": "천",
    "Warlock": "천"
}

# 역할별 한국어 표시명
ROLE_DISPLAY_KR = {
    "TANK": "탱커",
    "HEALER": "힐러",
    "MELEE_DPS": "근딜",
    "RANGED_DPS": "원딜"
}

# 역할별 우선순위 (정렬용)
ROLE_PRIORITY = {
    "TANK": 1,
    "HEALER": 2,
    "MELEE_DPS": 3,
    "RANGED_DPS": 4
}

class WoWRoleMapper:
    """WoW 역할 매핑 클래스"""
    
    @staticmethod
    def get_detailed_role(class_name: str, spec_name: str) -> str:
        """직업과 전문화로 세분화된 역할 반환"""
        # 정규화
        class_key = class_name.strip().title() if class_name else ""
        spec_key = spec_name.strip().title() if spec_name else ""
        
        # 직접 매칭
        role_key = (class_key, spec_key)
        if role_key in CLASS_SPEC_ROLES:
            return CLASS_SPEC_ROLES[role_key]
        
        # 부분 매칭 시도 (전문화만으로)
        for (cls, spec), role in CLASS_SPEC_ROLES.items():
            if cls.lower() == class_key.lower() and spec.lower() in spec_key.lower():
                return role
        
        # 기본값: 알 수 없으면 DPS로 간주
        print(f">>> 알 수 없는 직업/전문화 조합: {class_name}/{spec_name}")
        return "MELEE_DPS"
    
    @staticmethod
    def get_armor_type(class_name: str) -> str:
        """직업별 장비 소재 반환"""
        class_key = class_name.strip().title() if class_name else ""
        
        if class_key in CLASS_ARMOR_TYPE:
            return CLASS_ARMOR_TYPE[class_key]
        
        print(f">>> 알 수 없는 직업: {class_name}")
        return "알 수 없음"
    
    @staticmethod
    def get_role_display_kr(role: str) -> str:
        """역할의 한국어 표시명 반환"""
        return ROLE_DISPLAY_KR.get(role, role)
    
    @staticmethod
    def get_role_priority(role: str) -> int:
        """역할별 정렬 우선순위 반환"""
        return ROLE_PRIORITY.get(role, 99)
    
    @staticmethod
    def get_legacy_role(detailed_role: str) -> str:
        """기존 시스템 호환용 - 세분화된 역할을 기본 역할로 변환"""
        if detailed_role in ["MELEE_DPS", "RANGED_DPS"]:
            return "DPS"
        return detailed_role

# 편의 함수들
def get_character_role(class_name: str, spec_name: str) -> str:
    """캐릭터의 세분화된 역할 반환 (편의 함수)"""
    return WoWRoleMapper.get_detailed_role(class_name, spec_name)

def get_character_armor_type(class_name: str) -> str:
    """캐릭터의 장비 소재 반환 (편의 함수)"""
    return WoWRoleMapper.get_armor_type(class_name)

def get_role_korean(role: str) -> str:
    """역할의 한국어 이름 반환 (편의 함수)"""
    return WoWRoleMapper.get_role_display_kr(role)

def sort_by_role(participants: list, role_key: str = "character_role") -> list:
    """역할별로 참여자 정렬 (편의 함수)"""
    return sorted(participants, key=lambda x: WoWRoleMapper.get_role_priority(x.get(role_key, "")))

# 테스트 함수
def test_role_mapping():
    """역할 매핑 테스트"""
    print(">>> WoW 역할 매핑 테스트 시작")
    
    # 테스트 케이스들
    test_cases = [
        ("Warrior", "Protection"),
        ("Warrior", "Fury"),
        ("Priest", "Holy"),
        ("Priest", "Shadow"),
        ("Hunter", "Survival"),
        ("Hunter", "Beast Mastery"),
        ("Mage", "Fire"),
        ("Monk", "Brewmaster"),
        ("Death Knight", "Blood"),
        ("Evoker", "Devastation")
    ]
    
    print("\n>>> 역할 매핑 테스트:")
    for class_name, spec_name in test_cases:
        role = get_character_role(class_name, spec_name)
        armor = get_character_armor_type(class_name)
        role_kr = get_role_korean(role)
        print(f">>>   {class_name} {spec_name} -> {role} ({role_kr}), 방어구: {armor}")
    
    # 정렬 테스트
    test_participants = [
        {"name": "딜러1", "character_role": "RANGED_DPS"},
        {"name": "힐러1", "character_role": "HEALER"},
        {"name": "탱커1", "character_role": "TANK"},
        {"name": "딜러2", "character_role": "MELEE_DPS"},
    ]
    
    sorted_participants = sort_by_role(test_participants)
    print("\n>>> 정렬 테스트:")
    for p in sorted_participants:
        print(f">>>   {p['name']} ({get_role_korean(p['character_role'])})")

if __name__ == "__main__":
    test_role_mapping()