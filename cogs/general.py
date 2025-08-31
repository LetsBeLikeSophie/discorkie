# import json
# import discord
# from discord.ui import Select, View
# from discord.ext import commands
# from discord import app_commands, Interaction, ForumChannel, ui
# import os
# import aiohttp

# class General(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     @app_commands.command(name="길드원", description="닉네임에 특정 글자를 포함한 길드원들을 찾아줘요!")
#     @app_commands.describe(keyword="찾고 싶은 키워드 (예: 긔, 딜, 힐)")
#     async def find_guild_members(self, interaction: Interaction, keyword: str):
#         await interaction.response.defer(ephemeral=True)

#         file_path = "member.txt"
#         if not os.path.exists(file_path):
#             await interaction.followup.send("💾 member.txt 파일이 없어요!")
#             return

#         with open(file_path, "r", encoding="utf-8") as f:
#             lines = f.readlines()

#         matching = []
#         for line in lines:
#             if "-" not in line:
#                 continue
#             name, _ = line.strip().split("-", 1)
#             if keyword in name:
#                 matching.append(name)

#         if matching:
#             msg = f"🔍 '{keyword}' 를 포함한 부캐는 총 {len(matching)}명이에요!\n\n"
#             msg += "\n".join(f"- {name}" for name in matching)
#             await interaction.followup.send(msg)
#         else:
#             await interaction.followup.send(f"❌ '{keyword}' 를 포함한 부캐를 찾을 수 없어요!")

#     @app_commands.command(name="길드명단", description="(비수긔전용) 길드원 명단을 가져와 저장해요")
#     async def fetch_guild_roster(self, interaction: Interaction):
#         await interaction.response.defer(ephemeral=True)

#         # 사용자 ID 체크
#         if interaction.user.id != 1111599410594467862:
#             await interaction.followup.send("이 명령어는 비수긔만 사용할 수 있어요! 😣")
#             return

#         token = await self.get_blizzard_token()
#         if token is None:
#             await interaction.followup.send("Blizzard 인증에 실패했어요 😢")
#             return

#         url = (
#             "https://kr.api.blizzard.com/data/wow/guild/hyjal/"
#             "%EC%9A%B0%EB%8B%B9%ED%83%95%ED%83%95-%EC%8A%A4%ED%86%B0%EC%9C%88%EB%93%9C-%EC%A7%80%EA%B5%AC%EB%8C%80"
#             "/roster?namespace=profile-kr&locale=ko_KR"
#         )
#         headers = {"Authorization": f"Bearer {token}"}

#         async with aiohttp.ClientSession() as session:
#             async with session.get(url, headers=headers) as resp:
#                 if resp.status != 200:
#                     await interaction.followup.send(f"명단 요청 실패... 상태 코드: {resp.status}")
#                     return

#                 data = await resp.json()
#                 members = data.get("members", [])

#                 names = []
#                 for m in members:
#                     char = m.get("character")
#                     if char:
#                         name = char.get("name")
#                         slug = char.get("realm", {}).get("slug")
#                         if name and slug:
#                             names.append(f"{name}-{slug}")

#                 name_str = "\n".join(names)

#                 with open("member.txt", "w", encoding="utf-8") as f:
#                     f.write(name_str)

#                 await interaction.followup.send(f"총 {len(names)}명의 길드원 명단을 저장했어요! 📝")


                

# def setup(bot):
#     bot.add_cog(General(bot))