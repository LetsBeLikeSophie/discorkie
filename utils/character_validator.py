# utils\character_validator.py

import aiohttp
import urllib.parse

async def validate_character(realm: str, character_name: str) -> bool:
    """
    Raider.IO API를 사용해 캐릭터의 유효성을 검사합니다.
    
    Args:
        realm (str): 서버명 (예: "Azshara", "Hyjal")
        character_name (str): 캐릭터명 (예: "물고긔")
    
    Returns:
        bool: 캐릭터가 존재하면 True, 없거나 오류시 False
    """
    try:
        # URL 인코딩
        encoded_name = urllib.parse.quote(character_name)
        encoded_realm = urllib.parse.quote(realm)
        
        url = f"https://raider.io/api/v1/characters/profile?region=kr&realm={encoded_realm}&name={encoded_name}"
        
        print(f">>> 캐릭터 유효성 검사 시작: {character_name}-{realm}")
        print(f">>> API 요청 URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f">>> API 응답 상태 코드: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    # 필수 필드 확인
                    if 'name' in data and 'realm' in data:
                        print(f">>> 캐릭터 유효성 검사 성공: {data['name']}-{data['realm']}")
                        return True
                    else:
                        print(">>> 응답 데이터에 필수 필드가 없음")
                        return False
                        
                elif response.status == 404:
                    print(f">>> 캐릭터를 찾을 수 없음: {character_name}-{realm}")
                    return False
                else:
                    print(f">>> API 요청 실패: HTTP {response.status}")
                    return False
                    
    except aiohttp.ClientError as e:
        print(f">>> 네트워크 오류 발생: {e}")
        return False
    except Exception as e:
        print(f">>> 예상치 못한 오류 발생: {e}")
        return False

async def get_character_info(realm: str, character_name: str) -> dict:
    """
    Raider.IO API를 사용해 캐릭터 정보를 가져옵니다.
    
    Args:
        realm (str): 서버명 (예: "Azshara", "Hyjal")  
        character_name (str): 캐릭터명 (예: "물고긔")
    
    Returns:
        dict: 캐릭터 정보 딕셔너리, 실패시 빈 딕셔너리
    """
    try:
        # URL 인코딩
        encoded_name = urllib.parse.quote(character_name)
        encoded_realm = urllib.parse.quote(realm)
        
        url = f"https://raider.io/api/v1/characters/profile?region=kr&realm={encoded_realm}&name={encoded_name}"
        
        print(f">>> 캐릭터 정보 조회 시작: {character_name}-{realm}")
        print(f">>> API 요청 URL: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                print(f">>> API 응답 상태 코드: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f">>> 캐릭터 정보 조회 성공: {data.get('name', 'Unknown')}-{data.get('realm', 'Unknown')}")
                    return data
                else:
                    print(f">>> 캐릭터 정보 조회 실패: HTTP {response.status}")
                    return {}
                    
    except aiohttp.ClientError as e:
        print(f">>> 네트워크 오류 발생: {e}")
        return {}
    except Exception as e:
        print(f">>> 예상치 못한 오류 발생: {e}")
        return {}