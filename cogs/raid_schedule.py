# import discord
# from discord.ext import commands
# from discord import app_commands, Interaction
# from discord.ui import View, Button
# from datetime import datetime
# from .database import db
# from .character_manager import handle_raid_signup

# class RaidSignupView(View):
#     """레이드 신청 버튼 뷰"""
#     def __init__(self, event_id: int):
#         super().__init__(timeout=None)  # 영구 버튼
#         self.event_id = event_id

#     @discord.ui.button(label="⚔️ 참가 신청", style=discord.ButtonStyle.primary)
#     async def signup_button(self, interaction: Interaction, button: Button):
#         """참가 신청 버튼 - character_manager로 위임"""
#         await handle_raid_signup(interaction, self.event_id, self)

#     @discord.ui.button(label="❌ 참가 취소", style=discord.ButtonStyle.danger)
#     async def cancel_button(self, interaction: Interaction, button: Button):
#         """참가 취소 버튼"""
#         try:
#             print(f">>> 참가 취소 버튼 클릭: 사용자 {interaction.user.id}, 이벤트 {self.event_id}")
            
#             success = await db.cancel_signup(self.event_id, str(interaction.user.id))
            
#             if success:
#                 await interaction.response.send_message(
#                     "✅ 참가 신청이 취소되었습니다.",
#                     ephemeral=True
#                 )
                
#                 # 메시지 업데이트
#                 await self.update_raid_message(interaction)
#             else:
#                 await interaction.response.send_message(
#                     "❌ 취소할 신청이 없습니다.",
#                     ephemeral=True
#                 )
                
#         except Exception as e:
#             print(f">>> 참가 취소 오류: {e}")
#             if not interaction.response.is_done():
#                 await interaction.response.send_message(
#                     "❌ 오류가 발생했습니다. 관리자에게 문의해주세요.",
#                     ephemeral=True
#                 )

#     @discord.ui.button(label="📋 신청자 목록", style=discord.ButtonStyle.secondary)
#     async def list_button(self, interaction: Interaction, button: Button):
#         """신청자 목록 버튼"""
#         try:
#             print(f">>> 신청자 목록 버튼 클릭: 이벤트 {self.event_id}")
            
#             signups = await db.get_event_signups(self.event_id)
#             event = await db.get_event(self.event_id)
            
#             if not signups:
#                 await interaction.response.send_message(
#                     "📋 아직 신청한 사람이 없습니다.",
#                     ephemeral=True
#                 )
#                 return
            
#             # 역할별로 분류
#             tanks = []
#             healers = []
#             dps = []
#             unassigned = []
            
#             for signup in signups:
#                 role = signup.get('character_role', '').lower()
#                 name_info = f"{signup['character_name']}"
#                 if signup.get('character_class'):
#                     name_info += f" ({signup['character_class']})"
                
#                 if role in ['탱커', 'tank']:
#                     tanks.append(name_info)
#                 elif role in ['힐러', 'healer']:
#                     healers.append(name_info)
#                 elif role in ['딜러', 'dps', 'dealer']:
#                     dps.append(name_info)
#                 else:
#                     unassigned.append(name_info)
            
#             # 메시지 구성
#             embed = discord.Embed(
#                 title=f"📋 {event['title']} 신청자 목록",
#                 color=0x00ff00,
#                 timestamp=datetime.now()
#             )
            
#             embed.add_field(
#                 name=f"🛡️ 탱커 ({len(tanks)}명)",
#                 value="\n".join(tanks) if tanks else "없음",
#                 inline=True
#             )
            
#             embed.add_field(
#                 name=f"💚 힐러 ({len(healers)}명)",
#                 value="\n".join(healers) if healers else "없음",
#                 inline=True
#             )
            
#             embed.add_field(
#                 name=f"⚔️ 딜러 ({len(dps)}명)",
#                 value="\n".join(dps) if dps else "없음",
#                 inline=True
#             )
            
#             if unassigned:
#                 embed.add_field(
#                     name=f"❓ 역할 미설정 ({len(unassigned)}명)",
#                     value="\n".join(unassigned),
#                     inline=False
#                 )
            
#             embed.add_field(
#                 name="📊 전체",
#                 value=f"총 {len(signups)}명 / 최대 {event['max_participants']}명",
#                 inline=False
#             )
            
#             await interaction.response.send_message(embed=embed, ephemeral=True)
            
#         except Exception as e:
#             print(f">>> 신청자 목록 오류: {e}")
#             if not interaction.response.is_done():
#                 await interaction.response.send_message(
#                     "❌ 신청자 목록을 불러오는 중 오류가 발생했습니다.",
#                     ephemeral=True
#                 )

#     async def update_raid_message(self, interaction: Interaction):
#         """레이드 메시지 업데이트"""
#         try:
#             print(f">>> 레이드 메시지 업데이트 시작: 이벤트 {self.event_id}")
            
#             # 현재 신청자 수와 이벤트 정보 가져오기
#             signups = await db.get_event_signups(self.event_id)
#             event = await db.get_event(self.event_id)
            
#             print(f">>> 신청자 수: {len(signups)}, 최대: {event['max_participants']}")
            
#             try:
#                 # 원본 메시지 가져오기
#                 original_message = await interaction.original_response()
                
#                 if original_message and original_message.embeds:
#                     embed = original_message.embeds[0]
                    
#                     # 신청자 수 필드 찾아서 업데이트
#                     for i, field in enumerate(embed.fields):
#                         if "현재 신청자" in field.name or "신청자" in field.value:
#                             embed.set_field_at(
#                                 i,
#                                 name="👥 현재 신청자",
#                                 value=f"{len(signups)}명 / {event['max_participants']}명",
#                                 inline=field.inline
#                             )
#                             break
                    
#                     # 메시지 수정
#                     await original_message.edit(embed=embed, view=self)
#                     print(f">>> 레이드 메시지 업데이트 완료")
                    
#             except discord.NotFound:
#                 print(f">>> 원본 메시지를 찾을 수 없음")
#             except discord.HTTPException as e:
#                 print(f">>> 메시지 수정 HTTP 오류: {e}")
#             except Exception as e:
#                 print(f">>> 메시지 수정 기타 오류: {e}")
                
#         except Exception as e:
#             print(f">>> 레이드 메시지 업데이트 오류: {e}")

# class RaidSchedule(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     async def cog_load(self):
#         """Cog 로드 시 데이터베이스 연결"""
#         try:
#             await db.create_pool()
#             print(">>> RaidSchedule Cog 로드 완료")
#         except Exception as e:
#             print(f">>> RaidSchedule Cog 로드 오류: {e}")

#     async def cog_unload(self):
#         """Cog 언로드 시 데이터베이스 연결 해제"""
#         try:
#             await db.close_pool()
#             print(">>> RaidSchedule Cog 언로드 완료")
#         except Exception as e:
#             print(f">>> RaidSchedule Cog 언로드 오류: {e}")

#     @app_commands.command(name="레이드생성", description="새로운 레이드를 생성해요!")
#     @app_commands.describe(
#         title="레이드 제목",
#         description="레이드 설명",
#         max_participants="최대 참가자 수 (기본: 20명)"
#     )
#     async def create_raid(self, interaction: Interaction, title: str, 
#                          description: str = "", max_participants: int = 20):
#         """레이드 생성"""
#         try:
#             print(f">>> 레이드 생성 시작: {title} by {interaction.user.id}")
            
#             # 이벤트 생성
#             event_id = await db.create_event(
#                 event_name=title,
#                 title=title,
#                 description=description,
#                 creator_discord_id=str(interaction.user.id),
#                 max_participants=max_participants
#             )
            
#             print(f">>> 이벤트 ID 생성됨: {event_id}")
            
#             # 레이드 정보 embed 생성
#             embed = discord.Embed(
#                 title=f"⚔️ {title}",
#                 description=description or "레이드 설명이 없습니다.",
#                 color=0xff6600,
#                 timestamp=datetime.now()
#             )
            
#             embed.add_field(name="👑 생성자", value=interaction.user.mention, inline=True)
#             embed.add_field(name="👥 현재 신청자", value="0명 / {}명".format(max_participants), inline=True)
#             embed.add_field(name="📅 생성일", value=datetime.now().strftime("%Y-%m-%d %H:%M"), inline=True)
            
#             embed.set_footer(text=f"레이드 ID: {event_id}")
            
#             # 버튼 뷰 추가
#             view = RaidSignupView(event_id)
            
#             print(f">>> 레이드 메시지 전송 시작")
#             await interaction.response.send_message(embed=embed, view=view)
#             print(f">>> 레이드 생성 완료: ID {event_id}")
            
#         except Exception as e:
#             print(f">>> 레이드 생성 오류: {e}")
#             if not interaction.response.is_done():
#                 await interaction.response.send_message(
#                     "❌ 레이드 생성 중 오류가 발생했습니다. 관리자에게 문의해주세요.",
#                     ephemeral=True
#                 )

# async def setup(bot):
#     await bot.add_cog(RaidSchedule(bot))