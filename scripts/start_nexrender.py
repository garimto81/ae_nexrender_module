"""
Nexrender 서버 및 워커 시작 스크립트

Python subprocess를 사용하여 Nexrender 서버와 워커를 동시에 시작합니다.

사용법:
    # 서버+워커 동시 시작
    python scripts/start_nexrender.py

    # 서버만 시작
    python scripts/start_nexrender.py --server-only

    # 워커만 시작 (서버가 이미 실행 중일 때)
    python scripts/start_nexrender.py --worker-only

    # 커스텀 포트
    python scripts/start_nexrender.py --port 4000

    # After Effects 경로 지정
    python scripts/start_nexrender.py --ae-binary "C:/Program Files/Adobe/Adobe After Effects 2024/Support Files/aerender.exe"
"""

import argparse
import subprocess
import time
from pathlib import Path


def find_aerender():
    """After Effects aerender.exe 경로 자동 탐색"""
    common_paths = [
        r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\aerender.exe",
        r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\aerender.exe",
        r"C:\Program Files\Adobe\Adobe After Effects CC 2022\Support Files\aerender.exe",
        r"C:\Program Files\Adobe\Adobe After Effects CC 2021\Support Files\aerender.exe",
        r"C:\Program Files\Adobe\Adobe After Effects CC 2020\Support Files\aerender.exe",
    ]

    for path in common_paths:
        if Path(path).exists():
            return path

    return None


def parse_args():
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="Nexrender 서버 및 워커 시작 스크립트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=3000,
        help="Nexrender 서버 포트 (기본: 3000)",
    )

    parser.add_argument(
        "--server-only",
        action="store_true",
        help="서버만 시작 (워커 제외)",
    )

    parser.add_argument(
        "--worker-only",
        action="store_true",
        help="워커만 시작 (서버 제외)",
    )

    parser.add_argument(
        "--ae-binary",
        type=str,
        default=None,
        help="After Effects aerender.exe 경로 (자동 탐색되지 않을 경우)",
    )

    parser.add_argument(
        "--workpath",
        type=str,
        default=None,
        help="Nexrender 워커 작업 디렉토리",
    )

    return parser.parse_args()


def get_project_root() -> Path:
    """프로젝트 루트 경로 반환"""
    return Path(__file__).parent.parent


def start_server(port: int) -> subprocess.Popen:
    """Nexrender 서버 시작"""
    project_root = get_project_root()

    # npx를 사용하여 로컬 설치된 nexrender-server 실행
    cmd = ["npx", "nexrender-server", "--port", str(port)]
    print(f"[Nexrender] 서버 시작: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(project_root),
        shell=True,  # Windows에서 npx 실행을 위해 필요
    )

    return process


def start_worker(
    host: str, ae_binary: str | None = None, workpath: str | None = None
) -> subprocess.Popen:
    """Nexrender 워커 시작"""
    project_root = get_project_root()

    # npx를 사용하여 로컬 설치된 nexrender-worker 실행
    cmd = ["npx", "nexrender-worker", "--host", host]

    if ae_binary:
        cmd.extend(["--binary", ae_binary])

    if workpath:
        cmd.extend(["--workpath", workpath])

    print(f"[Nexrender] 워커 시작: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(project_root),
        shell=True,  # Windows에서 npx 실행을 위해 필요
    )

    return process


def stream_output(process: subprocess.Popen, prefix: str):
    """프로세스 출력을 실시간으로 스트리밍"""
    try:
        for line in process.stdout:
            print(f"[{prefix}] {line.rstrip()}")
    except Exception:
        pass


def main():
    """메인 엔트리포인트"""
    args = parse_args()

    processes = []
    host = f"http://localhost:{args.port}"

    # After Effects 경로 확인
    ae_binary = args.ae_binary or find_aerender()
    if not args.server_only and not ae_binary:
        print("[경고] After Effects aerender.exe를 찾을 수 없습니다.")
        print("  --ae-binary 옵션으로 경로를 지정하세요.")
        print(
            '  예: --ae-binary "C:/Program Files/Adobe/Adobe After Effects 2024/Support Files/aerender.exe"'
        )
    elif ae_binary:
        print(f"[Nexrender] After Effects: {ae_binary}")

    print(f"[Nexrender] 서버 URL: {host}")
    print("=" * 60)

    try:
        # 서버 시작
        if not args.worker_only:
            server_proc = start_server(args.port)
            processes.append(("Server", server_proc))
            time.sleep(2)  # 서버 시작 대기

        # 워커 시작
        if not args.server_only:
            worker_proc = start_worker(host, ae_binary, args.workpath)
            processes.append(("Worker", worker_proc))

        print("=" * 60)
        print("[Nexrender] Ctrl+C로 종료")
        print("=" * 60)

        # 출력 스트리밍 (메인 스레드에서)
        import threading

        threads = []
        for prefix, proc in processes:
            t = threading.Thread(target=stream_output, args=(proc, prefix), daemon=True)
            t.start()
            threads.append(t)

        # 프로세스 종료 대기
        for _, proc in processes:
            proc.wait()

    except KeyboardInterrupt:
        print("\n[Nexrender] 종료 신호 수신...")

    finally:
        # 모든 프로세스 종료
        for prefix, proc in processes:
            if proc.poll() is None:
                print(f"[Nexrender] {prefix} 종료 중...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

        print("[Nexrender] 종료 완료")


if __name__ == "__main__":
    main()
