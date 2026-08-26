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

# 게임 스레드만 보는 항목. 렌더 스레드가 프레임을 잡으면 신호가 묻히므로
# 기본으로 -nullrhi 를 붙인다. GPU·드로우 항목은 여기 넣지 않는다.
CPU_ONLY = {"tickvstimer", "bpvscpp", "castimplements", "getallactors", "childactor"}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "none"


def use_nullrhi(args, profile: str) -> bool:
    """cpu 프로파일은 게임 스레드 신호를 분리하고, full 은 실제 프레임을 본다.

    -nullrhi 를 걸면 gpu_ms 와 fps 가 의미를 잃는다. GPU 시간과 프레임레이트를
    비교하려면 full 프로파일이 필요하다. 그래서 두 벌을 따로 돌린다.
    """
    if profile == "cpu":
        return args.scenario.lower() in CPU_ONLY
    return False


def wrap_affinity(cmd: list[str], mask: str) -> list[str]:
    """윈도우에서 프로세스를 특정 코어에 묶는다.

    13900KF 같은 하이브리드 CPU 는 게임 스레드가 P코어와 E코어를 오가면 프레임
    시간이 크게 흔들린다. 측정 전에 묶어두는 편이 낫다.
    """
    if not mask:
        return cmd
    # cmd 를 하나의 문자열로 합쳐 넘기면 subprocess 가 그것을 다시 통째로 인용하고,
    # start 는 명령 전체를 프로그램 경로로 해석해 "지정된 프로그램을 실행할 수 없습니다"
    # 로 죽는다. 토큰을 그대로 펼쳐야 한다.
    # 앞의 "" 는 start 의 창 제목이다. 이게 없으면 공백 있는 exe 경로가 제목으로 먹힌다.
    return ["cmd", "/c", "start", "/affinity", mask, "/wait", "/b", "", *cmd]


def build_command(args, n: int, mode: str, repeat: int, out_dir: Path, profile: str) -> list[str]:
    cmd = [
        str(args.engine),
        str(args.project),
        "-game",
        f"-bench={args.scenario}",
        f"-N={n}",
        f"-warmupsec={args.warmup_sec}",
        f"-measuresec={args.measure_sec}",
        f"-repeat={repeat}",
        f"-machineid={args.machine_id}",
        f"-out={out_dir}",
        f"-tickgroup={args.tickgroup}",
        f"-profile={profile}",
        "-fixedseed",
        "-unattended",
        "-nopause",
        "-nosound",
        "-nosplash",
        "-windowed",
        "-resx=1280",
        "-resy=720",
        "-log",
        f"-abslog={out_dir / 'run.log'}",
    ]
    if mode:
        cmd.append(f"-mode={mode}")
    if args.scenario.lower() not in NO_FIXED_TIMESTEP:
        cmd.append("-benchmark")
    if use_nullrhi(args, profile):
        cmd.append("-nullrhi")
    if args.affinity:
        cmd.append(f"-affinity={args.affinity}")
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
    parser.add_argument("--warmup-sec", type=float, default=3.0,
                        help="클럭이 안정될 때까지 버리는 시간")
    parser.add_argument("--measure-sec", type=float, default=10.0,
                        help="측정 창. 프레임 수가 아니라 시간으로 자른다")
    parser.add_argument("--affinity", default="",
                        help="16진 코어 마스크. 하이브리드 CPU 는 P코어에 고정한다. "
                             "예: 13900KF 의 P코어 16스레드는 FFFF")
    parser.add_argument("--out", default=str(REPO_ROOT / "results"))
    parser.add_argument("--trace", default="",
                        help="Insights 채널. 기본은 끔. 측정 스윕에서 cpu 채널을 켜면 "
                             "액터 1만 개 × 수천 프레임의 이벤트가 쏟아져 계측 오버헤드가 "
                             "숫자를 오염시킨다. 원인 분석용 trace 는 별도 실행으로 뜬다. "
                             "예: --repeats 1 --trace cpu,frame,counters,bookmark,gpu")
    parser.add_argument("--profile", choices=("cpu", "full", "both"), default="both",
                        help="cpu 는 -nullrhi 로 게임 스레드만, full 은 실제 RHI 로 "
                             "GPU 시간과 fps 까지. both 는 둘 다 돌려 A/B 로 붙인다")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if platform.system() != "Windows" and not args.dry_run:
        print("측정은 Windows 물리 머신에서만 한다. 명령만 보려면 --dry-run 을 쓴다.",
              file=sys.stderr)
        return 2

    ns = [int(x) for x in args.n.split(",") if x.strip()]
    modes = [m.strip() for m in args.mode.split(",")] if args.mode else [""]
    date = datetime.date.today().isoformat()

    profiles = ["cpu", "full"] if args.profile == "both" else [args.profile]
    planned = len(ns) * len(modes) * args.repeats * len(profiles)
    est_min = planned * (args.warmup_sec + args.measure_sec + 8.0) / 60.0
    print(f"{args.scenario}: N {len(ns)}종 × mode {len(modes)}종 × 반복 {args.repeats} = {planned}회")
    print(f"  워밍업 {args.warmup_sec}s + 측정 {args.measure_sec}s · "
          f"프로파일 {'/'.join(profiles)} · affinity={args.affinity or '없음'} · "
          f"trace={args.trace or '끔'}")
    print(f"  예상 소요 약 {est_min:.0f}분 (엔진 기동 시간 포함)")

    failures = 0
    for profile in profiles:
      for n in ns:
        for mode in modes:
            for repeat in range(args.repeats):
                name = f"{slug(args.scenario)}_{profile}_N{n}_{slug(mode)}_r{repeat}"
                out_dir = Path(args.out) / args.machine_id / date / name
                cmd = wrap_affinity(
                    build_command(args, n, mode, repeat, out_dir, profile), args.affinity)

                if args.dry_run:
                    # dry-run 은 디렉터리를 만들지 않는다. 빈 폴더가 저장소에 남는다.
                    print(" ".join(cmd))
                    continue

                out_dir.mkdir(parents=True, exist_ok=True)

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
