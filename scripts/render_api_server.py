#!/usr/bin/env python
"""
AE-Nexrender 렌더링 API 서버 실행 스크립트

독립적으로 실행 가능한 API 서버입니다.

사용법:
    # 개발 모드 (핫 리로드)
    python scripts/render_api_server.py --env dev --reload

    # 프로덕션 모드 (멀티 워커)
    python scripts/render_api_server.py --env prod --workers 4

    # 커스텀 포트
    python scripts/render_api_server.py --port 8080
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(level: str = "INFO") -> None:
    """로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_env_file(env: str) -> None:
    """환경별 .env 파일 로드"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[Warning] python-dotenv 미설치 - .env 파일 로드 생략")
        return

    # 환경별 .env 파일 경로
    env_files = [
        PROJECT_ROOT / f".env.{env}",
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / ".env",
    ]

    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            print(f"[Config] 환경 파일 로드: {env_file}")
            break


def main() -> None:
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="AE-Nexrender 렌더링 API 서버",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
    # 개발 모드
    python scripts/render_api_server.py --env dev --reload

    # 프로덕션 모드
    python scripts/render_api_server.py --env prod --workers 4

    # 커스텀 설정
    python scripts/render_api_server.py --host 0.0.0.0 --port 8080 --log-level DEBUG
        """,
    )

    # 환경 설정
    parser.add_argument(
        "--env",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="실행 환경 (기본: dev)",
    )

    # 서버 설정
    parser.add_argument(
        "--host",
        default=None,
        help="바인딩 호스트 (기본: 환경변수 API_HOST 또는 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="바인딩 포트 (기본: 환경변수 API_PORT 또는 8000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="워커 프로세스 수 (기본: 1)",
    )

    # 개발 옵션
    parser.add_argument(
        "--reload",
        action="store_true",
        help="코드 변경 시 자동 리로드 (개발 모드용)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="로그 레벨",
    )

    # 설정 파일
    parser.add_argument(
        "--config",
        default="config/api_config.yaml",
        help="설정 파일 경로 (기본: config/api_config.yaml)",
    )

    args = parser.parse_args()

    # 환경 설정
    os.environ["ENV"] = args.env
    load_env_file(args.env)

    # 로깅 설정
    log_level = args.log_level or ("DEBUG" if args.env == "dev" else "INFO")
    setup_logging(log_level)

    # 서버 설정
    host = args.host or os.getenv("API_HOST", "0.0.0.0")
    port = args.port or int(os.getenv("API_PORT", "8000"))
    workers = args.workers if args.workers > 1 else 1

    # 개발 모드 옵션
    reload_enabled = args.reload or args.env == "dev"

    # 설정 파일 경로 환경변수 설정
    os.environ["CONFIG_PATH"] = args.config

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║            AE-Nexrender 렌더링 API 서버                        ║
╠═══════════════════════════════════════════════════════════════╣
║  환경: {args.env:<10}                                          ║
║  호스트: {host:<15}                                        ║
║  포트: {port:<5}                                               ║
║  워커: {workers:<3}개                                            ║
║  리로드: {'ON' if reload_enabled else 'OFF':<5}                                         ║
║  설정: {args.config:<20}                           ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    try:
        import uvicorn

        # Uvicorn 실행 설정
        uvicorn_config = {
            "app": "api.server:app",
            "host": host,
            "port": port,
            "log_level": log_level.lower(),
            "reload": reload_enabled,
        }

        # 멀티 워커 (리로드와 동시 사용 불가)
        if workers > 1 and not reload_enabled:
            uvicorn_config["workers"] = workers

        # 리로드 시 감시 디렉토리
        if reload_enabled:
            uvicorn_config["reload_dirs"] = [
                str(PROJECT_ROOT / "api"),
                str(PROJECT_ROOT / "config"),
                str(PROJECT_ROOT / "lib"),
            ]

        uvicorn.run(**uvicorn_config)

    except ImportError:
        print("[Error] uvicorn 미설치. 설치: pip install uvicorn")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[Server] 서버 종료")
    except Exception as e:
        print(f"[Error] 서버 시작 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
