import discord
from discord import app_commands
from functools import wraps

GUILD_ID = 1275099769731022971  # 우당탕탕 스톰윈드 지구대 서버 ID

def guild_only():
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            # 서버 ID 체크
            if interaction.guild is None or interaction.guild.id != GUILD_ID:
                await interaction.response.send_message(
                    "❌ 이 명령어는 우당탕탕 스톰윈드 지구대에서만 사용할 수 있어요!", 
                    ephemeral=True
                )
                return
            
            # 원래 함수 실행
            return await func(self, interaction, *args, **kwargs)
        
        # 슬래시 명령어 속성 보존
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        if hasattr(func, '__annotations__'):
            wrapper.__annotations__ = func.__annotations__
        
        return wrapper
    return decorator