#!/usr/bin/env python3
"""Insights trace 에서 타이머 통계를 뽑아 CSV 로 떨군다.

왜 필요한가. 러너가 재는 game_ms 는 프레임 전체의 게임 스레드 시간이다.
"그 시간이 어느 함수에서 나왔는가"는 답하지 못한다. 그건 Insights 가 답한다.
러너 숫자와 Insights 숫자가 어긋나면 러너를 의심해야 하므로, 대조 자체가 검증이다.

trace 는 측정 스윕과 따로 뜬다. 측정 중에 cpu 채널을 켜면 계측 오버헤드가
결과를 바꾼다. 순서는 이렇다.

  1) trace 없이 스윕을 돌려 숫자를 얻는다
  2) 조건마다 1회씩 trace 를 켜고 다시 돌린다
  3) 그 trace 를 이 스크립트로 뽑거나 Insights GUI 로 연다

주의. 아래 콘솔 명령 이름은 엔진 버전에 따라 다르다. 5.8 에서 처음 돌릴 때
실패하면 --list-candidates 로 후보를 보고 --cmd 로 바꿔 지정한다.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# 우선 시도할 내보내기 명령. 실패하면 후보를 안내한다.
DEFAULT_EXPORT_CMD = "TimingInsights.ExportTimerStatistics"
CANDIDATES = [
    "TimingInsights.ExportTimerStatistics",
    "TimingInsights.ExportTimers",
    "TimingInsights.ExportThreads",
    "TimingInsights.ExportTimingEvents",
]


def find_insights(explicit: str) -> Path | None:
    if explicit:
        return Path(explicit)
    found = shutil.which("UnrealInsights") or shutil.which("UnrealInsights.exe")
    return Path(found) if found else None


def export_one(insights: Path, trace: Path, out_csv: Path, cmd: str, dry: bool) -> bool:
    argv = [
        str(insights),
        f"-OpenTraceFile={trace}",
        "-AutoQuit",
        "-NoUI",
        f'-ExecOnAnalysisCompleteCmd={cmd} "{out_csv}"',
    ]
    if dry:
        print(" ".join(argv))
        return True

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(argv, capture_output=True, text=True)
    if out_csv.exists() and out_csv.stat().st_size > 0:
        print(f"  {trace.parent.name} → {out_csv.name}")
        return True

    print(f"  {trace.parent.name} 실패 (exit={result.returncode})", file=sys.stderr)
    tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
    for line in tail:
        print(f"    {line}", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_dir", nargs="?", default="")
    parser.add_argument("--insights", default="",
                        help="UnrealInsights 실행 파일 경로. "
                             "보통 Engine/Binaries/Win64/UnrealInsights.exe")
    parser.add_argument("--cmd", default=DEFAULT_EXPORT_CMD)
    parser.add_argument("--list-candidates", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.list_candidates:
        print("시도해 볼 명령 후보:")
        for candidate in CANDIDATES:
            print(f"  {candidate}")
        print("\nInsights 를 GUI 로 띄운 뒤 콘솔에서 'TimingInsights.' 를 치고 "
              "자동완성으로 실제 이름을 확인하는 게 가장 빠르다.")
        return 0

    if not args.results_dir:
        parser.error("results_dir 이 필요하다")

    insights = find_insights(args.insights)
    if insights is None or (not args.dry_run and not insights.exists()):
        print("UnrealInsights 실행 파일을 찾지 못했다. --insights 로 지정한다.",
              file=sys.stderr)
        return 2

    traces = sorted(Path(args.results_dir).rglob("run.utrace"))
    if not traces:
        print(f"{args.results_dir} 아래에 run.utrace 가 없다. "
              f"--trace 를 켜고 다시 돌렸는지 확인한다.", file=sys.stderr)
        return 1

    print(f"trace {len(traces)}개, 명령 `{args.cmd}`")
    failed = 0
    for trace in traces:
        if not export_one(insights, trace, trace.parent / "timers.csv",
                          args.cmd, args.dry_run):
            failed += 1

    if failed:
        print(f"\n{failed}/{len(traces)}개 실패. --list-candidates 로 다른 명령을 "
              f"확인하거나, GUI 로 열어 수동으로 본다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
