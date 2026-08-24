#!/usr/bin/env python3
"""summary.json 들을 모아 하나의 CSV 로 정규화한다.

머신이 섞이면 실패한다. CPU 가 다르면 곡선의 절대값이 통째로 이동해서
한 표에 올린 순간 그 표는 아무것도 말해주지 않는다.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

COLUMNS = [
    "machine_id", "cpu", "gpu", "ram_gb", "os", "engine_version", "build_config",
    "rhi", "affinity", "core_count", "substrate", "scenario", "profile", "param_n", "param_extra",
    "repeat_index", "warmup_seconds", "measured_seconds", "measured_frames",
    "average_fps", "hitch_ratio", "render_bound", "warnings",
    "frame_ms_median", "frame_ms_p95", "frame_ms_min", "frame_ms_max",
    "scenario_ms_median", "scenario_ms_p95",
    "game_ms_median", "game_ms_p95",
    "render_ms_median", "gpu_ms_median",
]


def flatten(summary: dict) -> dict:
    env = summary.get("environment", {})
    scal = env.get("scalability", {})

    def stat(block: str, key: str):
        return summary.get(block, {}).get(key)

    row = {
        "machine_id": env.get("machine_id", ""),
        "cpu": env.get("cpu", ""),
        "gpu": env.get("gpu", ""),
        "ram_gb": env.get("ram_gb", ""),
        "os": env.get("os", ""),
        "engine_version": env.get("engine_version", ""),
        "build_config": env.get("build_config", ""),
        "rhi": env.get("rhi", ""),
        "affinity": env.get("affinity", ""),
        "core_count": env.get("core_count", ""),
        "substrate": env.get("substrate", ""),
        "scenario": summary.get("scenario", ""),
        "profile": summary.get("profile", "full"),
        "param_n": summary.get("param_n", ""),
        "param_extra": summary.get("param_extra", ""),
        "repeat_index": summary.get("repeat_index", ""),
        "warmup_seconds": summary.get("warmup_seconds", ""),
        "measured_seconds": summary.get("measured_seconds", ""),
        "measured_frames": summary.get("measured_frames", ""),
        "average_fps": summary.get("average_fps", ""),
        "hitch_ratio": summary.get("hitch_ratio", ""),
        "render_bound": summary.get("render_bound", ""),
        "warnings": " | ".join(summary.get("warnings", [])),
        "frame_ms_median": stat("frame_ms", "median"),
        "frame_ms_p95": stat("frame_ms", "p95"),
        "frame_ms_min": stat("frame_ms", "min"),
        "frame_ms_max": stat("frame_ms", "max"),
        "scenario_ms_median": stat("scenario_ms", "median"),
        "scenario_ms_p95": stat("scenario_ms", "p95"),
        "game_ms_median": stat("game_ms", "median"),
        "game_ms_p95": stat("game_ms", "p95"),
        "render_ms_median": stat("render_ms", "median"),
        "gpu_ms_median": stat("gpu_ms", "median"),
    }
    row["_scalability"] = scal
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_dir")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    root = Path(args.results_dir)
    files = sorted(root.rglob("summary.json"))
    if not files:
        print(f"{root} 아래에 summary.json 이 없다.", file=sys.stderr)
        return 1

    rows = []
    for path in files:
        try:
            rows.append(flatten(json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            print(f"{path}: JSON 파싱 실패 — {exc}", file=sys.stderr)
            return 1

    machines = {r["machine_id"] for r in rows}
    if len(machines) > 1:
        print("머신이 섞여 있다. 하나씩 따로 처리한다:", file=sys.stderr)
        for m in sorted(machines):
            print(f"  - {m or '(빈 machine_id)'}", file=sys.stderr)
        return 1

    engines = {r["engine_version"] for r in rows}
    configs = {r["build_config"] for r in rows}
    if len(engines) > 1 or len(configs) > 1:
        print(f"엔진 버전 {sorted(engines)} / 빌드 구성 {sorted(configs)} 이 섞여 있다.",
              file=sys.stderr)
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)}행 → {out}")
    print(f"머신 {machines.pop()} · 엔진 {engines.pop()} · 구성 {configs.pop()}")

    # 러너가 붙인 경고를 여기서 한 번 더 올린다. 조용히 넘어가면 안 되는 것들이다.
    flagged = [r for r in rows if r.get("warnings")]
    if flagged:
        print(f"\n러너가 경고를 남긴 실행 {len(flagged)}/{len(rows)}건:", file=sys.stderr)
        seen = {}
        for row in flagged:
            for w in row["warnings"].split(" | "):
                key = w.split(".")[0][:60]
                seen[key] = seen.get(key, 0) + 1
        for key, count in sorted(seen.items(), key=lambda kv: -kv[1]):
            print(f"  {count:3d}회  {key}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
