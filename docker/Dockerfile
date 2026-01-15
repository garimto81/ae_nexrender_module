# ============================================================================
# AE-Nexrender Worker Dockerfile
# Python 3.11 기반 렌더링 워커 이미지
# ============================================================================

FROM python:3.11-slim

# 메타데이터
LABEL maintainer="Backend Team"
LABEL version="2.0.0"
LABEL description="AE-Nexrender 렌더링 워커 모듈"

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# 앱 코드 복사
COPY lib/ ./lib/
COPY worker/ ./worker/

# 환경변수 설정
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 헬스체크 (30초 간격, 10초 타임아웃, 5초 시작 유예, 3회 재시도)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 포트 노출
EXPOSE 8080

# 워커 시작
CMD ["python", "-m", "worker.main"]
