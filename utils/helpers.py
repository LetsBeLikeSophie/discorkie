# utils/helpers.py
import traceback
from functools import wraps


class Logger:
    @staticmethod
    def info(message):
        print(f">>> {message}")
    
    @staticmethod
    def error(message, exception=None):
        print(f">>> {message}")
        if exception:
            print(f">>> 스택 추적: {traceback.format_exc()}")


def handle_interaction_errors(func):
    """인터랙션 에러 처리 데코레이터"""
    @wraps(func)
    async def wrapper(self, interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)
        except Exception as e:
            Logger.error(f"{func.__name__} 오류: {e}", e)
            
            # 이미 응답했는지 확인
            if not interaction.response.is_done():
                await interaction.response.send_message(">>> 처리 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.followup.send(">>> 처리 중 오류가 발생했습니다.", ephemeral=True)
    return wrapper


class ParticipationStatus:
    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    DECLINED = "declined"


class Emojis:
    ROCKET = "🚀"
    STAR = "⭐"


def clean_nickname(nickname: str) -> str:
    """닉네임에서 이모티콘 제거"""
    return nickname.replace(Emojis.ROCKET, "").replace(Emojis.STAR, "").strip()