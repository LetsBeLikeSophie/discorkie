GUILD_ID = 1275099769731022971  # 우당탕탕 스톰윈드 지구대 서버 ID

def guild_only():
    def decorator(func):
        async def wrapper(self, interaction, *args, **kwargs):
            if interaction.guild.id != GUILD_ID:
                return await interaction.response.send_message("❌ 서버 전용!", ephemeral=True)
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator