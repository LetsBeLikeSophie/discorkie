# discorkie

디스코드 서버에서 길드 레이드 일정·참가자·캐릭터 인증을 관리하는 WoW(월드 오브 워크래프트) 길드 운영 봇.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![discord.py](https://img.shields.io/badge/discord.py-5865F2?style=flat-square&logo=discord&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)

## 주요 기능

- **캐릭터 자동 인증** — 유저가 디스코드 닉네임을 캐릭터명으로 바꾸면 Raider.io/Blizzard API로 실존 여부를 확인해서, 서버가 하나로 특정되면 🚀, 여러 서버에 동명 캐릭터가 있어 모호하면 ⭐ 이모지를 자동으로 붙이고 DB에 연결
- **레이드 일정** — `/일정`으로 다가오는 이벤트 조회, `/일정공지`로 참가 신청 버튼이 달린 임베드 발송. 확정/미정/불참 인원이 실시간으로 집계됨
- **관리자 참가자 관리** — 드롭다운으로 일정을 고른 뒤 참가자 추가·상태 변경·제거를 버튼/모달로 처리, 변경되면 관련 메시지가 자동으로 갱신됨
- **와우 토큰 시세** (`/토큰`) — Blizzard OAuth로 토큰 발급 후 실시간 KR 서버 시세 조회
- **이번 주 어픽스** (`/어픽스`) — Raider.io API
- 그 외 길드 통계, 레이드 진행도, 아이템 정보(Wowhead), 보조스탯 조회

## 기술 스택

- Python, discord.py (슬래시 커맨드 + 재시작 후에도 유지되는 영속 View)
- PostgreSQL (asyncpg, `guild_bot` 스키마) — 길드원·캐릭터·일정·참가 이력 관리
- 외부 API: Blizzard Battle.net OAuth, Raider.io, Wowhead

## 로컬 실행

```bash
pip install -r requirements.txt
python main.py
```

`.env`에 `DISCORD_TOKEN`, `BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`, PostgreSQL 접속 정보가 필요합니다.
