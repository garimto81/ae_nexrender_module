# AE-Nexrender 배포 가이드

## 개요

AE-Nexrender는 After Effects 렌더링 자동화를 위한 독립 워커 서비스입니다. 이 문서는 프로덕션 환경 배포 절차를 설명합니다.

## 아키텍처

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Dashboard     │─────▶│  Supabase        │◀─────│   Worker        │
│   (Next.js)     │      │  render_queue    │      │   (Python)      │
└─────────────────┘      └──────────────────┘      └────────┬────────┘
                                                            │
                                                            ▼
                         ┌──────────────────┐      ┌─────────────────┐
                         │  Output Files    │◀─────│   Nexrender     │
                         │  (NAS/Local)     │      │   (Node.js)     │
                         └──────────────────┘      └─────────────────┘
```

## 사전 요구사항

### 시스템 요구사항

- Windows 10/11 또는 Windows Server 2019+
- Python 3.11+
- Node.js 18+ (Nexrender용)
- Adobe After Effects CC 2022+
- 최소 16GB RAM (권장 32GB)
- SSD 저장소

### 소프트웨어 의존성

```powershell
# Python 패키지
pip install -r requirements.txt

# Node.js 패키지 (Nexrender)
npm install
```

## 환경 설정

### 1. 환경변수 설정

`.env.example`을 `.env`로 복사하고 실제 값으로 변경:

```bash
# 필수
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Nexrender
NEXRENDER_URL=http://localhost:3000
NEXRENDER_SECRET=your-secret-key

# 경로
OUTPUT_DIR=D:/output
AEP_TEMPLATE_DIR=D:/templates
NAS_OUTPUT_PATH=//NAS/renders

# 렌더링
RENDER_TIMEOUT=1800
MAX_RETRIES=3
```

### 2. Supabase 마이그레이션

```powershell
# Supabase CLI 설치
npm install -g supabase

# 마이그레이션 적용
supabase db push --db-url "postgresql://..."

# 또는 SQL 직접 실행
psql -f migrations/000_full_migration_no_fk.sql
```

### 3. 경로 매핑 설정

Docker 환경에서는 경로 매핑이 필요합니다:

```bash
# .env
PATH_MAPPINGS=/app/templates:D:/templates,/app/output:D:/output
```

## 배포 방법

### 방법 1: 직접 실행 (개발/테스트)

```powershell
# 1. Nexrender 서버 + 워커 시작
npm start

# 2. Python 워커 시작 (별도 터미널)
python -m worker.main

# 3. API 서버 시작 (선택적)
python -m api.server
```

### 방법 2: Docker Compose (프로덕션 권장)

```yaml
# docker-compose.yml
version: '3.8'

services:
  nexrender-server:
    build: ./docker
    ports:
      - "3000:3000"
    environment:
      - NEXRENDER_SECRET=${NEXRENDER_SECRET}

  nexrender-worker:
    build: ./docker
    command: nexrender-worker --host nexrender-server
    depends_on:
      - nexrender-server
    volumes:
      - ${TEMPLATE_DIR_HOST}:/app/templates
      - ${OUTPUT_DIR_HOST}:/app/output

  ae-worker:
    build: .
    command: python -m worker.main
    depends_on:
      - nexrender-server
    environment:
      - SUPABASE_URL
      - SUPABASE_SERVICE_KEY
      - NEXRENDER_URL=http://nexrender-server:3000
    volumes:
      - ${OUTPUT_DIR_HOST}:/app/output
```

```powershell
# 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f ae-worker

# 중지
docker-compose down
```

### 방법 3: Windows 서비스 (프로덕션)

NSSM(Non-Sucking Service Manager)을 사용한 서비스 등록:

```powershell
# NSSM 설치
choco install nssm

# 서비스 등록
nssm install AE-Nexrender-Worker "python" "-m worker.main"
nssm set AE-Nexrender-Worker AppDirectory "C:\claude\ae_nexrender_module"
nssm set AE-Nexrender-Worker AppEnvironmentExtra "SUPABASE_URL=..." "SUPABASE_SERVICE_KEY=..."

# 서비스 시작
nssm start AE-Nexrender-Worker
```

## 헬스체크

### HTTP 엔드포인트

워커는 `/health` 엔드포인트를 제공합니다:

```powershell
# 헬스체크
curl http://localhost:8080/health

# 응답 예시
{
  "status": "healthy",
  "worker_id": "worker-abc123",
  "uptime_seconds": 3600,
  "jobs_processed": 42,
  "last_job_at": "2024-01-19T10:30:00Z"
}
```

### Docker 헬스체크

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

## 모니터링

### 로그 위치

```
logs/
├── worker.log          # 워커 메인 로그
├── nexrender.log       # Nexrender 서버 로그
└── error.log           # 에러 전용 로그
```

### 로그 레벨 설정

```bash
# .env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Supabase 대시보드

- `render_queue` 테이블에서 작업 상태 모니터링
- `status` 필드: pending → preparing → rendering → encoding → completed/failed

## 트러블슈팅

### 일반적인 문제

#### 1. Nexrender 연결 실패

```
Error: ECONNREFUSED 127.0.0.1:3000
```

**해결책:**
```powershell
# Nexrender 서버 상태 확인
curl http://localhost:3000/api/v1/jobs

# 서버 재시작
npm run server
```

#### 2. After Effects 라이선스 오류

```
Error: After Effects is not licensed
```

**해결책:**
- After Effects가 활성화되어 있는지 확인
- 렌더 전용 라이선스 사용 시 `--no-gui` 옵션 확인

#### 3. 출력 파일 생성 실패

```
Error: Output file not found
```

**해결책:**
```powershell
# 출력 디렉토리 권한 확인
icacls D:\output

# AE Output Module 확인
# After Effects에서 "Alpha MOV" 템플릿이 있는지 확인
```

#### 4. NAS 복사 실패

```
Warning: NAS 디렉토리 접근 불가
```

**해결책:**
```powershell
# NAS 연결 상태 확인
net use

# NAS 드라이브 다시 매핑
net use Z: \\NAS\renders /persistent:yes
```

### 에러 코드

| 코드 | 설명 | 조치 |
|------|------|------|
| `RETRYABLE` | 네트워크/일시 오류 | 자동 재시도 |
| `NON_RETRYABLE` | 설정/파일 오류 | 수동 확인 필요 |
| `TIMEOUT` | 렌더링 타임아웃 | RENDER_TIMEOUT 증가 |

## 스케일링

### 다중 워커 구성

여러 워커를 실행하여 처리량 증가:

```powershell
# 워커 1
WORKER_ID=worker-1 python -m worker.main

# 워커 2
WORKER_ID=worker-2 python -m worker.main

# 워커 3
WORKER_ID=worker-3 python -m worker.main
```

### 주의사항

- 각 워커는 고유한 `WORKER_ID` 필요
- After Effects는 단일 인스턴스만 실행 가능
- 다중 워커 시 여러 PC 또는 VM 필요

## 백업 및 복구

### 중요 데이터

1. **환경 설정**: `.env` 파일
2. **매핑 설정**: `config/mappings/*.yaml`
3. **Supabase 데이터**: `render_queue` 테이블

### 복구 절차

```powershell
# 1. 코드 복원
git clone https://github.com/your-org/ae-nexrender-module.git

# 2. 환경 설정 복원
cp backup/.env .

# 3. 의존성 설치
pip install -r requirements.txt
npm install

# 4. 서비스 시작
docker-compose up -d
```

## 보안 권장사항

1. **API 키 관리**: 환경변수 또는 시크릿 매니저 사용
2. **네트워크 격리**: 내부 네트워크에서만 Nexrender 서버 접근
3. **파일 권한**: 출력 디렉토리 최소 권한 부여
4. **로그 정리**: 민감 정보 포함 로그 주기적 정리

## 지원

- 이슈 리포트: GitHub Issues
- 내부 문서: `docs/` 디렉토리
- 기술 지원: [담당자 연락처]
