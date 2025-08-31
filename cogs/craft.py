# import json
# import discord
# from discord.ext import commands
# from discord import app_commands
# from discord.ui import Select, View, Button
# import pandas as pd
# from datetime import datetime
# from utils import guild_only

# class CraftingCommands(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#         # /직업별제작템 명령어용 JSON 데이터 로드
#         with open('data/bis_crafting_items.json', 'r', encoding='utf-8') as f:
#             self.crafting_items = json.load(f)
#         # /제작하기 명령어용 CSV 데이터 로드
#         self.craftman_data = pd.read_csv("data/craftman.csv", sep='\t')


#     @app_commands.command(name="직업별제작템", description="직업과 특성을 선택해 제작 아이템과 장식을 보여줘요!")
#     @guild_only()
#     async def crafting(self, interaction: discord.Interaction):
#         roles = list(self.crafting_items.keys())
#         role_choices = [discord.SelectOption(label=role, value=role) for role in roles]
#         select_menu = Select(placeholder="직업을 선택해주세요 🎮", options=role_choices)
#         select_menu.callback = self.role_select
#         view = View()
#         view.add_item(select_menu)
#         # 나만 보게(ephemeral)
#         await interaction.response.send_message("💫 **직업을 선택해주세요!** 🤔", view=view)
    
#     async def role_select(self, interaction: discord.Interaction):
#         role = interaction.data['values'][0]
#         specs = list(self.crafting_items[role].keys())
#         spec_choices = [discord.SelectOption(label=spec, value=spec) for spec in specs]
#         select_menu = Select(placeholder="특성을 선택해주세요! 🧐", options=spec_choices)
#         select_menu.callback = lambda inter: self.spec_select(inter, role)
#         view = View()
#         view.add_item(select_menu)
#         await interaction.response.edit_message(content="✨ **특성을 선택해주세요!** 😄", view=view)

#     async def spec_select(self, interaction: discord.Interaction, role: str):
#         spec = interaction.data['values'][0]
#         gear_items = self.crafting_items[role][spec]["gear"]
#         embellishments = self.crafting_items[role][spec]["embellishments"]

#         msg = f"**{role} - {spec}** 제작 아이템과 장식 🌟\n\n"
#         msg += "**✨아이템:**\n"
#         for item in gear_items:
#             msg += f" - {item['name']}\n"
#         msg += "\n**🎀장식:**\n"
#         for emb in embellishments:
#             msg += f" - {emb['name']}\n"
#         msg += "\n아이템명을 복사해서 사용해 보세요! 📋\n"
#         view = View()
#         # URL 버튼 대신 콜백 버튼으로 제작 의뢰 흐름 시작
#         btn = Button(label="✨제작 의뢰하기", style=discord.ButtonStyle.primary)
#         btn.callback = lambda inter: self.crafting_request_callback(inter, role, spec, gear_items, embellishments)
#         view.add_item(btn)
#         view.add_item(Button(label="🔗출처:와우헤드", url="https://www.wowhead.com/ko/news/%EB%82%B4%EB%B6%80-%EC%A0%84%EC%9F%81-2-%EC%8B%9C%EC%A6%8C-%EB%82%B4-%EC%A7%81%EC%97%85-%EB%B0%8F-%EC%A0%9C%EC%9E%91-%EC%9E%A5%EB%B9%84-375567"))
#         await interaction.response.edit_message(content=msg, view=view)
    
#     async def crafting_request_callback(self, interaction: discord.Interaction, role: str, spec: str, gear_items: list, embellishments: list):
#         # JSON에 기록된 아이템/장식 정보를 합치기
#         combined = []
#         for item in gear_items:
#             combined.append({"type": "아이템", "name": item["name"]})
#         for emb in embellishments:
#             combined.append({"type": "장식", "name": emb["name"]})
#         view = SelectCraftingItemView(combined, interaction.user, self.bot)
#         await interaction.response.send_message("제작 의뢰할 아이템을 아래 드롭다운에서 선택해 주세요! 🥰", view=view)


#     @app_commands.command(name="제작하기", description="귀여운 제작 요청을 할 수 있어요~!")
#     @app_commands.describe(search="아이템명, 부위, 종류 중 검색할 단어를 입력해봐~!")
#     @guild_only() 
#     async def 제작하기(self, interaction: discord.Interaction, search: str):
#         await interaction.response.defer(ephemeral=True)
#         mask = self.craftman_data[['아이템명', '부위', '종류']].apply(
#             lambda col: col.str.contains(search, case=False, na=False)
#         )
#         filtered = self.craftman_data[mask.any(axis=1)]
#         if filtered.empty:
#             await interaction.followup.send("앗, 길드에 제작할 수 있는 사람이 없는 것 같아요... 😢")
#             return
#         elif len(filtered) == 1:
#             row = filtered.iloc[0]
#             if pd.isna(row['제작자명']) or not str(row['제작자명']).strip():
#                 await interaction.followup.send("앗, 이 아이템의 제작자가 등록되어 있지 않아요... 길드에 제작할 수 있는 사람이 없는 것 같아요! 😢")
#                 return
#             view = CraftRequestView(row, interaction.user, self.bot)
#             description = (
#                 f"찾은 아이템은 이렇답니다~!\n"
#                 f"**아이템명:** {row['아이템명']}\n"
#                 f"**부위:** {row['부위']}\n"
#                 f"**종류:** {row['종류']}\n"
#                 f"**제작자:** {row['제작자명']}\n\n"
#                 "이 아이템으로 제작요청 게시물을 올려볼까요? 💖"
#             )
#             await interaction.followup.send(description, view=view)
#         else:
#             view = SelectItemView(filtered, interaction.user, self.bot)
#             message = "검색 결과가 여러 개에요~! 아래에서 원하는 아이템을 골라봐~! 🥰"
#             await interaction.followup.send(message, view=view)

# ################################
# # CSV 데이터를 이용한 제작요청 관련 UI (/제작하기 명령어용)
# ################################
# class CraftRequestView(discord.ui.View):
#     def __init__(self, item_data, author, bot):
#         super().__init__(timeout=60)
#         self.item_data = item_data  # pandas.Series (CSV 레코드)
#         self.author = author
#         self.bot = bot
#         self.confirmed = False
    
#     @discord.ui.button(label="제작요청 💖", style=discord.ButtonStyle.primary)
#     async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user != self.author:
#             if not interaction.response.is_done():
#                 await interaction.response.send_message("이 버튼은 명령어를 실행한 사용자만 누를 수 있어요! 😊")
#             else:
#                 await interaction.followup.send("이 버튼은 명령어를 실행한 사용자만 누를 수 있어요! 😊")
#             return
#         maker = str(self.item_data.get('제작자명', '')).strip()
#         if not maker:
#             if not interaction.response.is_done():
#                 await interaction.response.send_message("앗, 이 아이템의 제작자가 등록되어 있지 않아요... 길드에 제작할 수 있는 사람이 없는 것 같아요! 😢")
#             else:
#                 await interaction.followup.send("앗, 이 아이템의 제작자가 등록되어 있지 않아요... 길드에 제작할 수 있는 사람이 없는 것 같아요! 😢")
#             return
#         self.confirmed = True
#         if not interaction.response.is_done():
#             await interaction.response.send_message("제작요청 게시물을 작성할게요! ✨ <#1359876862154772704> 확인하세요!")
#         else:
#             await interaction.followup.send("제작요청 게시물을 작성할게요! ✨")
#         target_channel = self.bot.get_channel(1359876862154772704)
#         if target_channel is None:
#             await interaction.followup.send("타겟 채널을 찾지 못했어요... 😢")
#             return
#         tag_obj = discord.utils.get(target_channel.available_tags, id=1359877087179047063)
#         if not tag_obj:
#             await interaction.followup.send("태그를 찾지 못했어요... 😢")
#             return
#         now = datetime.now()
#         title = f"{now.month}/{now.day} {self.item_data['아이템명']} 제작요청"
#         content = f"{interaction.user.mention} 님의 제작요청이 도착했어요! 💕\n> 인게임에서 길드주문으로 \n> ## {self.item_data['아이템명']}\n> 주문 넣는거 잊지마세요!"
#         await target_channel.create_thread(
#             name=title,
#             content=content,
#             auto_archive_duration=1440,
#             applied_tags=[tag_obj]
#         )
#         self.stop()

#     @discord.ui.button(label="취소 😅", style=discord.ButtonStyle.danger)
#     async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user != self.author:
#             if not interaction.response.is_done():
#                 await interaction.response.send_message("이 버튼은 명령어를 실행한 사용자만 사용할 수 있어요! 😊")
#             else:
#                 await interaction.followup.send("이 버튼은 명령어를 실행한 사용자만 사용할 수 있어요! 😊")
#             return
#         if not interaction.response.is_done():
#             await interaction.response.send_message("제작요청을 취소했어요~! 😌")
#         else:
#             await interaction.followup.send("제작요청을 취소했어요~! 😌")
#         self.stop()

# ################################
# # CSV 데이터를 이용한 드롭다운 UI (/제작하기 명령어용)
# ################################
# class SelectItemView(discord.ui.View):
#     def __init__(self, items, author, bot):
#         super().__init__(timeout=60)
#         self.items = items
#         self.author = author
#         self.bot = bot
#         self.selected_item = None
#         options = []
#         for index, row in items.iterrows():
#             parts = []
#             for col in ['아이템명', '부위', '종류', '기타']:
#                 value = row[col]
#                 if pd.notna(value):
#                     parts.append(str(value))
#             label = " / ".join(parts)
#             options.append(discord.SelectOption(label=label, value=str(index)))
#         self.select = discord.ui.Select(placeholder="원하는 아이템을 골라봐~! 🥰", options=options)
#         self.select.callback = self.select_callback
#         self.add_item(self.select)
    
#     async def select_callback(self, interaction: discord.Interaction):
#         if interaction.user != self.author:
#             await interaction.response.send_message("명령어를 실행한 사용자만 선택할 수 있어요! 😊")
#             return
#         index = int(self.select.values[0])
#         self.selected_item = self.items.loc[index]
#         if pd.isna(self.selected_item['제작자명']) or not str(self.selected_item['제작자명']).strip():
#             await interaction.response.send_message("앗, 이 아이템의 제작자가 등록되어 있지 않아요... 길드에 제작할 수 있는 사람이 없는 것 같아요! 😢")
#             self.stop()
#             return
#         desc = (
#             f"**아이템명:** {self.selected_item['아이템명']}\n"
#             f"**부위:** {self.selected_item['부위']}\n"
#             f"**종류:** {self.selected_item['종류']}\n"

#             "\n\n제작 가능한 길드원을 찾았어요!\n이 아이템으로 제작요청 게시물을 올릴까요? 💕"
#         )
#         view = CraftRequestView(self.selected_item, self.author, self.bot)
#         await interaction.response.send_message(desc, view=view)
#         self.stop()

# ################################
# # JSON 데이터를 이용한 제작의뢰 관련 UI (/직업별제작템 명령어용)
# ################################
# class SelectCraftingItemView(discord.ui.View):
#     def __init__(self, items, author, bot):
#         super().__init__(timeout=60)
#         self.items = items  # [{"type": "아이템"/"장식", "name": str}, ...]
#         self.author = author
#         self.bot = bot
#         self.selected_item = None
#         options = []
#         for item in items:
#             # 접두어 ("아이템 - " 또는 "장식 - ") 제거 후 순수한 이름만 사용
#             name = item['name']
#             if name.startswith("아이템 - "):
#                 name = name[len("아이템 - "):]
#             elif name.startswith("장식 - "):
#                 name = name[len("장식 - "):]
#             options.append(discord.SelectOption(label=name, value=name))
#         self.select = discord.ui.Select(placeholder="아이템 선택해주세요! 🥰", options=options)
#         self.select.callback = self.select_callback
#         self.add_item(self.select)
    
#     async def select_callback(self, interaction: discord.Interaction):
#         if interaction.user != self.author:
#             await interaction.response.send_message("명령어를 실행한 사용자만 선택할 수 있어요! 😊")
#             return
#         selected_name = self.select.values[0]
#         for item in self.items:
#             temp_name = item['name']
#             if temp_name.startswith("아이템 - "):
#                 temp_name = temp_name[len("아이템 - "):]
#             elif temp_name.startswith("장식 - "):
#                 temp_name = temp_name[len("장식 - "):]
#             if temp_name == selected_name:
#                 self.selected_item = item
#                 break
#         # CSV 검색: craftman.csv에서 선택한 아이템명을 기준으로 검색하여 제작자, 부위, 종류 등 정보를 얻음
#         csv_data = None
#         for cog in self.bot.cogs.values():
#             if hasattr(cog, "craftman_data"):
#                 csv_data = cog.craftman_data
#                 break
#         if csv_data is None:
#             await interaction.response.send_message("CSV 데이터가 로드되지 않았어요.")
#             self.stop()
#             return
#         csv_data['clean_name'] = csv_data['아이템명'].str.strip().str.lower()
#         selected_clean = selected_name.strip().lower()
#         filtered = csv_data[csv_data['clean_name'] == selected_clean]
#         if filtered.empty:
#             await interaction.response.send_message("앗, 길드에 제작할 수 있는 사람이 없는 것 같아요... 😢")
#             self.stop()
#             return
#         row = filtered.iloc[0]
#         maker = str(row.get('제작자명', '')).strip()
#         if not maker:
#             await interaction.response.send_message("앗, 이 아이템의 제작자가 등록되어 있지 않아요... 길드에 제작할 수 있는 사람이 없는 것 같아요! 😢")
#             self.stop()
#             return
#         # 구성된 CSV 정보를 사용해 확인 메시지 작성
#         desc = (
#             f"**아이템명:** {row['아이템명']}\n"
#             f"**부위:** {row['부위']}\n"
#             f"**종류:** {row['종류']}\n"
            
#             "\n\n제작 가능한 길드원을 찾았어요!\n이 아이템으로 제작요청 게시물을 올릴까요? 💕"
#         )
#         # self.selected_item에 CSV 정보를 반영하여 전달
#         self.selected_item = {
#             '아이템명': row['아이템명'],
#             '부위': row['부위'],
#             '종류': row['종류'],
#             '제작자명': row['제작자명']
#         }
#         view = CraftRequestViewJSON(self.selected_item, self.author, self.bot)
#         await interaction.response.send_message(desc, view=view)
#         self.stop()

# class CraftRequestViewJSON(discord.ui.View):
#     def __init__(self, item_data, author, bot):
#         super().__init__(timeout=60)
#         self.item_data = item_data  # CSV 정보: '아이템명', '부위', '종류', '제작자명'
#         self.author = author
#         self.bot = bot
#         self.confirmed = False
    
#     @discord.ui.button(label="제작요청 💖", style=discord.ButtonStyle.primary)
#     async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user != self.author:
#             if not interaction.response.is_done():
#                 await interaction.response.send_message("이 버튼은 명령어를 실행한 사용자만 누를 수 있어요! 😊")
#             else:
#                 await interaction.followup.send("이 버튼은 명령어를 실행한 사용자만 누를 수 있어요! 😊")
#             return
#         self.confirmed = True
#         if not interaction.response.is_done():
#             await interaction.response.send_message("제작요청 게시물을 작성할게요! ✨")
#         else:
#             await interaction.followup.send("제작요청 게시물을 작성할게요! ✨")
#         target_channel = self.bot.get_channel(1359876862154772704)
#         if target_channel is None:
#             await interaction.followup.send("타겟 채널을 찾지 못했어요... 😢")
#             return
#         tag_obj = discord.utils.get(target_channel.available_tags, id=1359877087179047063)
#         if not tag_obj:
#             await interaction.followup.send("태그를 찾지 못했어요... 😢")
#             return
#         now = datetime.now()
#         title = f"{now.month}/{now.day} {self.item_data['아이템명']} 제작요청"
#         content = f"{interaction.user.mention} 님의 제작요청이 도착했어요! 💕\n> 인게임에서 길드주문으로 \n> ## {self.item_data['아이템명']}\n> 주문 넣는거 잊지마세요!"
#         await target_channel.create_thread(
#             name=title,
#             content=content,
#             auto_archive_duration=1440,
#             applied_tags=[tag_obj]
#         )
#         self.stop()
    
#     @discord.ui.button(label="취소 😅", style=discord.ButtonStyle.danger)
#     async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if interaction.user != self.author:
#             if not interaction.response.is_done():
#                 await interaction.response.send_message("이 버튼은 명령어를 실행한 사용자만 사용할 수 있어요! 😊")
#             else:
#                 await interaction.followup.send("이 버튼은 명령어를 실행한 사용자만 사용할 수 있어요! 😊")
#             return
#         if not interaction.response.is_done():
#             await interaction.response.send_message("제작요청을 취소했어요~! 😌")
#         else:
#             await interaction.followup.send("제작요청을 취소했어요~! 😌")
#         self.stop()

# async def setup(bot):
#     await bot.add_cog(CraftingCommands(bot))
