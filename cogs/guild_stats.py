import asyncio
import asyncpg
from typing import Dict, List, Tuple, Any, Optional
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, Select, Button
import os
from dotenv import load_dotenv

load_dotenv()

class StatsSelect(Select):
    def __init__(self, cog):
        self.cog = cog
        options = [
            discord.SelectOption(
                label="인기 TOP3", 
                value="popular_top3",
                description="가장 인기있는 직업, 전문화, 서버 TOP3!",
                emoji="🏆"
            ),
            discord.SelectOption(
                label="길드 랭킹", 
                value="rankings",
                description="업적점수 & 쐐기점수 TOP5 랭킹!",
                emoji="👑"
            ),
            discord.SelectOption(
                label="비율 분석",
                value="ratios", 
                description="성별, 진영, 서버 비율 분석!",
                emoji="📊"
            ),
            discord.SelectOption(
                label="특이한 통계",
                value="special_stats",
                description="가장 희귀한 조합과 특별한 통계들!",
                emoji="🎲"
            )
        ]
        super().__init__(placeholder="원하는 통계를 선택해주세요!", options=options)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        
        stat_type = self.values[0]
        
        try:
            if stat_type == "popular_top3":
                await self._show_popular_top3(interaction)
            elif stat_type == "rankings":
                await self._show_rankings(interaction)
            elif stat_type == "ratios":
                await self._show_ratios(interaction)
            elif stat_type == "special_stats":
                await self._show_special_stats(interaction)
        except Exception as e:
            print(f">>> 통계 조회 중 오류 발생: {e}")
            await interaction.followup.send("통계 조회 중 오류가 발생했어요 😢")

    async def _show_popular_top3(self, interaction: Interaction):
        """인기 TOP3 통계"""
        top3_stats = await self.cog.get_popular_top3()
        
        embed = discord.Embed(
            title="🏆 인기 TOP3 통계",
            description="우리 길드에서 가장 사랑받는 것들이에요! 💕",
            color=0xf39c12
        )
        
        # 인기 직업 TOP3
        job_text = "\n"
        for i, (job, count) in enumerate(top3_stats['top_classes'][:3], 1):
            medals = ["🥇", "🥈", "🥉"]
            job_text += f"{medals[i-1]} {job} ({count}명)\n"
        embed.add_field(name="💼 인기 직업 TOP3", value=job_text, inline=True)
        
        # 인기 전문화 TOP3
        spec_text = "\n"
        for i, (spec, count) in enumerate(top3_stats['top_specs'][:3], 1):
            medals = ["🥇", "🥈", "🥉"]
            spec_text += f"{medals[i-1]} {spec} ({count}명)\n"
        embed.add_field(name="⚔️ 인기 전문화 TOP3", value=spec_text, inline=True)
        
        # 인기 서버 TOP3
        realm_text = "\n"
        for i, (realm, count) in enumerate(top3_stats['top_realms'][:3], 1):
            medals = ["🥇", "🥈", "🥉"]
            realm_text += f"{medals[i-1]} {realm} ({count}명)\n"
        embed.add_field(name="🏠 인기 서버 TOP3", value=realm_text, inline=True)
        
        await interaction.followup.send(embed=embed)

    async def _show_rankings(self, interaction: Interaction):
        """랭킹 통계"""
        ranking_stats = await self.cog.get_rankings()
        
        embed = discord.Embed(
            title="👑 길드 랭킹",
            description="우리 길드의 최고 실력자들이에요! 짝짝짝~ 👏",
            color=0x9b59b6
        )
        
        # 업적점수 TOP5
        achievement_text = "\n"
        medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
        for i, (name, points) in enumerate(ranking_stats['achievement_ranking'][:5]):
            achievement_text += f"{medals[i]} {name} ({points:,}점)\n"
        embed.add_field(name="🏆 업적점수 TOP5", value=achievement_text, inline=False)
        
        # TODO: 쐐기점수 데이터가 있으면 추가
        # 현재는 업적점수만 표시하고 추후 확장 가능
        
        await interaction.followup.send(embed=embed)

    async def _show_ratios(self, interaction: Interaction):
        """비율 분석"""
        ratio_stats = await self.cog.get_ratios()
        
        embed = discord.Embed(
            title="📊 비율 분석",
            description="우리 길드의 균형감각을 확인해봐요! ⚖️",
            color=0x3498db
        )
        
        # 성별 비율
        male_ratio = ratio_stats['gender_ratio']['male']
        female_ratio = ratio_stats['gender_ratio']['female']
        embed.add_field(
            name="🚹🚺 성별 비율",
            value=f"남성 {male_ratio}% : 여성 {female_ratio}%\n{'남초 길드네요! 💪' if male_ratio > female_ratio else '여초 길드네요! 👑' if female_ratio > male_ratio else '완벽한 균형! 🎯'}",
            inline=False
        )
        
        # 진영 비율
        horde_ratio = ratio_stats['faction_ratio']['horde']
        alliance_ratio = ratio_stats['faction_ratio']['alliance']
        embed.add_field(
            name="⚡🔥 진영 비율", 
            value=f"호드 {horde_ratio}% : 얼라 {alliance_ratio}%\n{'호드가 우세해요! 🔥' if horde_ratio > alliance_ratio else '얼라가 우세해요! ⚡' if alliance_ratio > horde_ratio else '완벽한 균형! ⚖️'}",
            inline=False
        )
        
        # 역할군 비율
        role_ratio = ratio_stats['role_ratio']
        tank_ratio = role_ratio.get('탱', 0)
        heal_ratio = role_ratio.get('힐', 0) 
        dps_ratio = role_ratio.get('딜', 0)
        
        embed.add_field(
            name="⚔️ 역할군 비율",
            value=f"탱 {tank_ratio}% | 힐 {heal_ratio}% | 딜 {dps_ratio}%\n{'균형잡힌 구성이에요! 👍' if 10 <= tank_ratio <= 20 and 15 <= heal_ratio <= 25 else '역할 불균형이 있네요! 🤔'}",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

    async def _show_special_stats(self, interaction: Interaction):
        """특이한 통계"""
        special_stats = await self.cog.get_special_stats()
        
        embed = discord.Embed(
            title="🎲 특이한 통계",
            description="길드의 숨겨진 재미있는 사실들을 발견했어요! 🔍✨",
            color=0xe67e22
        )
        
        embed.add_field(
            name="🌟 가장 희귀한 조합",
            value=f"{special_stats['rarest_combo']}\n(단 {special_stats['rarest_count']}명뿐!)",
            inline=True
        )
        
        embed.add_field(
            name="👑 업적 대왕",
            value=f"{special_stats['achievement_king']}\n({special_stats['max_achievement']:,}점의 위엄!)",
            inline=True
        )
        
        embed.add_field(
            name="🏠 길드 본거지",
            value=f"{special_stats['main_realm']}\n({special_stats['main_realm_count']}명 거주중)",
            inline=True
        )
        
        embed.add_field(
            name="🎯 전문화 독점왕",
            value=f"{special_stats['dominant_spec']}\n(무려 {special_stats['dominant_spec_count']}명!)",
            inline=True
        )
        
        embed.add_field(
            name="🦄 외로운 전사",
            value=f"{special_stats['loneliest_spec']}\n(혼자서도 잘해요... 😢)",
            inline=True
        )
        
        embed.add_field(
            name="📊 길드 다양성",
            value=f"{'🌈 매우 다양해요!' if special_stats['diversity_score'] > 0.8 else '🌟 적당히 다양해요!' if special_stats['diversity_score'] > 0.6 else '🎯 비슷비슷해요!'}",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)

class StatsView(View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.add_item(StatsSelect(cog))

class GuildStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool: Optional[asyncpg.Pool] = None

    async def cog_load(self):
        """Cog 로드 시 DB 연결 풀 생성"""
        try:
            database_url = os.getenv("DATABASE_URL")
            self.pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=5
            )
            print(">>> 길드 통계 DB 연결 풀 생성 완료")
        except Exception as e:
            print(f">>> 길드 통계 DB 연결 실패: {e}")

    async def cog_unload(self):
        """Cog 언로드 시 DB 연결 풀 해제"""
        if self.pool:
            await self.pool.close()
            print(">>> 길드 통계 DB 연결 풀 해제 완료")

    async def execute_query(self, query: str, *params) -> List[tuple]:
        """데이터베이스 쿼리 실행"""
        if not self.pool:
            print(">>> DB 연결 풀이 없습니다")
            return []
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetch(query, *params)
                print(f">>> 쿼리 실행 완료: {len(result)}행 반환")
                return result
        except Exception as e:
            print(f">>> 데이터베이스 쿼리 오류: {e}")
            return []

    async def execute_single_query(self, query: str, *params) -> Optional[tuple]:
        """단일 결과 쿼리 실행"""
        if not self.pool:
            print(">>> DB 연결 풀이 없습니다")
            return None
        
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow(query, *params)
                print(f">>> 단일 쿼리 실행 완료")
                return result
        except Exception as e:
            print(f">>> 데이터베이스 쿼리 오류: {e}")
            return None

    @app_commands.command(name="길드통계", description="(실험실) 길드원들의 다양한 통계를 확인할 수 있어요!")
    async def guild_stats(self, interaction: Interaction):
        await interaction.response.defer()
        
        if not self.pool:
            await interaction.followup.send("데이터베이스 연결이 없어요 😢")
            return
        
        embed = discord.Embed(
            title="📊 우당탕탕 길드 통계",
            description="아래 드롭다운에서 원하는 통계를 선택해주세요! 💕\n\n*📅 9월 1일 기준 데이터로 재미로만 봐주세요~\n아직 업데이트 예정이 없어서 참고용으로만! 😊*",
            color=0x2c3e50
        )
        
        view = StatsView(self)
        await interaction.followup.send(embed=embed, view=view)

    async def get_popular_top3(self) -> Dict[str, Any]:
        """인기 TOP3 통계 조회"""
        print(">>> 인기 TOP3 통계 조회 시작")
        
        # 인기 직업 TOP3
        top_classes_query = """
        SELECT class, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY class 
        ORDER BY count DESC 
        LIMIT 3
        """
        top_classes_result = await self.execute_query(top_classes_query)
        top_classes = [(cls, cnt) for cls, cnt in top_classes_result] if top_classes_result else []
        
        # 인기 전문화 TOP3
        top_specs_query = """
        SELECT active_spec, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND active_spec IS NOT NULL
        GROUP BY active_spec 
        ORDER BY count DESC 
        LIMIT 3
        """
        top_specs_result = await self.execute_query(top_specs_query)
        top_specs = [(spec, cnt) for spec, cnt in top_specs_result] if top_specs_result else []
        
        # 인기 서버 TOP3
        top_realms_query = """
        SELECT realm, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY realm 
        ORDER BY count DESC 
        LIMIT 3
        """
        top_realms_result = await self.execute_query(top_realms_query)
        top_realms = [(realm, cnt) for realm, cnt in top_realms_result] if top_realms_result else []
        
        print(">>> 인기 TOP3 통계 조회 완료")
        return {
            'top_classes': top_classes,
            'top_specs': top_specs,
            'top_realms': top_realms
        }

    async def get_rankings(self) -> Dict[str, Any]:
        """랭킹 통계 조회"""
        print(">>> 랭킹 통계 조회 시작")
        
        # 업적점수 TOP5
        achievement_query = """
        SELECT character_name, achievement_points 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND achievement_points > 0
        ORDER BY achievement_points DESC 
        LIMIT 5
        """
        achievement_result = await self.execute_query(achievement_query)
        achievement_ranking = [(name, points) for name, points in achievement_result] if achievement_result else []
        
        print(">>> 랭킹 통계 조회 완료")
        return {
            'achievement_ranking': achievement_ranking
        }

    async def get_ratios(self) -> Dict[str, Any]:
        """비율 분석 조회"""
        print(">>> 비율 분석 조회 시작")
        
        # 성별 비율
        gender_query = """
        SELECT gender, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY gender
        """
        gender_result = await self.execute_query(gender_query)
        male_count = 0
        female_count = 0
        total_gender = 0
        
        for row in gender_result:
            if row[0] == '남성':
                male_count = row[1]
            elif row[0] == '여성':
                female_count = row[1]
            total_gender += row[1]
        
        gender_ratio = {
            'male': int((male_count / total_gender * 100)) if total_gender > 0 else 0,
            'female': int((female_count / total_gender * 100)) if total_gender > 0 else 0
        }
        
        # 진영 비율
        faction_query = """
        SELECT faction, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY faction
        """
        faction_result = await self.execute_query(faction_query)
        horde_count = 0
        alliance_count = 0
        total_faction = 0
        
        for row in faction_result:
            if row[0] == '호드':
                horde_count = row[1]
            elif row[0] == '얼라이언스':
                alliance_count = row[1]
            total_faction += row[1]
        
        faction_ratio = {
            'horde': int((horde_count / total_faction * 100)) if total_faction > 0 else 0,
            'alliance': int((alliance_count / total_faction * 100)) if total_faction > 0 else 0
        }
        
        # 역할군 비율
        role_query = """
        SELECT active_spec_role, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND active_spec_role IS NOT NULL
        GROUP BY active_spec_role
        """
        role_result = await self.execute_query(role_query)
        role_stats = {}
        total_role = 0
        
        for row in role_result:
            role_stats[row[0]] = row[1]
            total_role += row[1]
        
        role_ratio = {}
        for role, count in role_stats.items():
            role_ratio[role] = int((count / total_role * 100)) if total_role > 0 else 0
        
        print(">>> 비율 분석 조회 완료")
        return {
            'gender_ratio': gender_ratio,
            'faction_ratio': faction_ratio,
            'role_ratio': role_ratio
        }

    async def get_special_stats(self) -> Dict[str, Any]:
        """특이한 통계 조회"""
        print(">>> 특이한 통계 조회 시작")
        
        # 가장 희귀한 종족+직업 조합
        rarest_combo_query = """
        SELECT race || ' ' || class as combo, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY race, class 
        ORDER BY count ASC 
        LIMIT 1
        """
        rarest_combo_result = await self.execute_single_query(rarest_combo_query)
        rarest_combo = rarest_combo_result[0] if rarest_combo_result else "알 수 없음"
        rarest_count = rarest_combo_result[1] if rarest_combo_result else 0
        
        # 업적 대왕
        achievement_king_query = """
        SELECT character_name, achievement_points 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND achievement_points > 0
        ORDER BY achievement_points DESC 
        LIMIT 1
        """
        achievement_king_result = await self.execute_single_query(achievement_king_query)
        achievement_king = achievement_king_result[0] if achievement_king_result else "알 수 없음"
        max_achievement = achievement_king_result[1] if achievement_king_result else 0
        
        # 길드 본거지 (가장 많은 서버)
        main_realm_query = """
        SELECT realm, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY realm 
        ORDER BY count DESC 
        LIMIT 1
        """
        main_realm_result = await self.execute_single_query(main_realm_query)
        main_realm = main_realm_result[0] if main_realm_result else "알 수 없음"
        main_realm_count = main_realm_result[1] if main_realm_result else 0
        
        # 가장 많은 전문화 (독점왕)
        dominant_spec_query = """
        SELECT active_spec, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND active_spec IS NOT NULL
        GROUP BY active_spec 
        ORDER BY count DESC 
        LIMIT 1
        """
        dominant_spec_result = await self.execute_single_query(dominant_spec_query)
        dominant_spec = dominant_spec_result[0] if dominant_spec_result else "알 수 없음"
        dominant_spec_count = dominant_spec_result[1] if dominant_spec_result else 0
        
        # 가장 적은 전문화 (외로운 전사)
        loneliest_spec_query = """
        SELECT active_spec, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko' AND active_spec IS NOT NULL
        GROUP BY active_spec 
        HAVING COUNT(*) = 1
        LIMIT 1
        """
        loneliest_spec_result = await self.execute_single_query(loneliest_spec_query)
        loneliest_spec = loneliest_spec_result[0] if loneliest_spec_result else "없음"
        
        # 다양성 지수 계산 (심슨 다양성 지수 응용)
        diversity_query = """
        SELECT class, COUNT(*) as count 
        FROM guild_bot.guild_members 
        WHERE is_guild_member = TRUE AND language = 'ko'
        GROUP BY class
        """
        diversity_result = await self.execute_query(diversity_query)
        
        if diversity_result:
            total = sum(count for _, count in diversity_result)
            simpson_index = sum((count / total) ** 2 for _, count in diversity_result)
            diversity_score = 1 - simpson_index  # 1에 가까울수록 다양함
        else:
            diversity_score = 0
        
        print(">>> 특이한 통계 조회 완료")
        return {
            'rarest_combo': rarest_combo,
            'rarest_count': rarest_count,
            'achievement_king': achievement_king,
            'max_achievement': max_achievement,
            'main_realm': main_realm,
            'main_realm_count': main_realm_count,
            'dominant_spec': dominant_spec,
            'dominant_spec_count': dominant_spec_count,
            'loneliest_spec': loneliest_spec,
            'diversity_score': diversity_score
        }

async def setup(bot):
    await bot.add_cog(GuildStats(bot))