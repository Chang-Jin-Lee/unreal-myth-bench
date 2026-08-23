#!/usr/bin/env python3
"""벤치 실행 오케스트레이터.

반복은 프로세스 재시작 단위다. 한 프로세스 안에서 여러 번 재면 캐시가 데워져
뒤쪽 반복이 유리해지기 때문에, 여기서 매번 엔진을 새로 띄운다.

측정 조건은 docs/01-protocol.md 가 정한다. 여기 기본값을 바꾸면 그 이전 결과는
폐기 대상이다.
"""

import argparse
import datetime
import platform
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT = REPO_ROOT / "MythBench" / "MythBench.uproject"

# -benchmark 를 쓰면 고정 타임스텝이 되어 실제 경과 시간이 의미를 잃는다.
# 주기와 deadline 이 대상인 시나리오는 여기에 넣어 제외한다.
NO_FIXED_TIMESTEP = {"deadline"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "none"


def build_command(args, n: int, mode: str, repeat: int, out_dir: Path) -> list[str]:
    cmd = [
        str(args.engine),
        str(args.project),
        "-game",
        f"-bench={args.scenario}",
        f"-N={n}",
        f"-warmup={args.warmup}",
        f"-frames={args.frames}",
        f"-repeat={repeat}",
        f"-machineid={args.machine_id}",
        f"-out={out_dir}",
        f"-tickgroup={args.tickgroup}",
        "-fixedseed",
        "-unattended",
        "-nopause",
        "-nosound",
        "-nosplash",
        "-windowed",
        "-resx=1280",
        "-resy=720",
        "-log",
    ]
    if mode:
        cmd.append(f"-mode={mode}")
    if args.scenario.lower() not in NO_FIXED_TIMESTEP:
        cmd.append("-benchmark")
    if args.nullrhi:
        cmd.append("-nullrhi")
    if args.trace:
        cmd.append(f"-trace={args.trace}")
        cmd.append(f"-tracefile={out_dir / 'run.utrace'}")
    return cmd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--machine-id", required=True,
                        help="결과 경로에 들어간다. 머신마다 유일해야 한다")
    parser.add_argument("--engine", default="UnrealEditor-Cmd.exe",
                        help="UnrealEditor-Cmd 실행 파일 경로")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT))
    parser.add_argument("--n", default="10,100,1000,10000",
                        help="스윕 축. 쉼표로 구분")
    parser.add_argument("--mode", default="",
                        help="시나리오별 추가 축. 쉼표로 구분. 예: tick,timer,disabled")
    parser.add_argument("--tickgroup", default="prephysics")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=120)
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--out", default=str(REPO_ROOT / "results"))
    parser.add_argument("--trace", default="",
                        help="예: cpu,frame,counters,bookmark. 비우면 trace 끔")
    parser.add_argument("--nullrhi", action="store_true",
                        help="CPU 전용 항목과 CI 에서만. GPU·드로우 항목에는 쓰지 않는다")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Windows" and not args.dry_run:
        print("측정은 Windows 물리 머신에서만 한다. 명령만 보려면 --dry-run 을 쓴다.",
              file=sys.stderr)
        return 2

    ns = [int(x) for x in args.n.split(",") if x.strip()]
    modes = [m.strip() for m in args.mode.split(",")] if args.mode else [""]
    date = datetime.date.today().isoformat()

    planned = len(ns) * len(modes) * args.repeats
    print(f"{args.scenario}: N {len(ns)}종 × mode {len(modes)}종 × 반복 {args.repeats} = {planned}회")

    failures = 0
    for n in ns:
        for mode in modes:
            for repeat in range(args.repeats):
                name = f"{slug(args.scenario)}_N{n}_{slug(mode)}_r{repeat}"
                out_dir = Path(args.out) / args.machine_id / date / name
                out_dir.mkdir(parents=True, exist_ok=True)
                cmd = build_command(args, n, mode, repeat, out_dir)

                if args.dry_run:
                    print(" ".join(cmd))
                    continue

                print(f"  {name} ...", end="", flush=True)
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0 or not (out_dir / "summary.json").exists():
                    failures += 1
                    print(" 실패")
                    (out_dir / "stderr.txt").write_text(result.stderr or "", encoding="utf-8")
                else:
                    print(" 완료")

    if failures:
        print(f"{failures}회 실패. 각 디렉터리의 stderr.txt 와 run.log 를 본다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
