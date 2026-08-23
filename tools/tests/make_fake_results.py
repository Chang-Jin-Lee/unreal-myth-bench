#!/usr/bin/env python3
"""가짜 summary.json 을 만든다.

UE 가 없는 머신에서도 파서와 리포트 생성기를 끝까지 돌려볼 수 있게 하려는 것이다.
여기서 나오는 숫자는 측정값이 아니다. results/ 에 커밋하지 않는다.
"""

import argparse
import json
import random
from pathlib import Path

ENV = {
    "machine_id": "fake-machine",
    "cpu": "Fake CPU 16-Core",
    "gpu": "Fake GPU",
    "ram_gb": 32,
    "os": "Fake OS 1.0",
    "engine_version": "5.8.1-0+++UE5+Release-5.8",
    "build_config": "Development",
    "rhi": "D3D12",
    "substrate": False,
    "scalability": {"view_distance": 3, "shadow": 3, "texture": 3, "effects": 3},
}

# 모드별 (액터당 기울기 ms, 기본 비용 ms)
SLOPES = {"tick": (0.00042, 0.31), "timer": (0.00018, 0.31), "disabled": (0.0, 0.30)}


def block(value: float, jitter: float) -> dict:
    return {
        "median": round(value, 4),
        "p95": round(value * (1.0 + jitter * 1.8), 4),
        "min": round(value * 0.94, 4),
        "max": round(value * (1.0 + jitter * 4.0), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--machine-id", default=ENV["machine_id"])
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    root = Path(args.out)

    for n in (10, 100, 1000, 10000):
        for mode, (slope, base) in SLOPES.items():
            for repeat in range(args.repeats):
                game = base + slope * n
                game *= 1.0 + rng.uniform(-0.015, 0.015)
                jitter = rng.uniform(0.02, 0.06)

                env = dict(ENV, machine_id=args.machine_id)
                summary = {
                    "scenario": "TickVsTimer",
                    "param_n": n,
                    "param_extra": f"mode={mode};tickgroup=prephysics",
                    "repeat_index": repeat,
                    "warmup_frames": 120,
                    "measured_frames": 600,
                    "frame_ms": block(game + 0.22, jitter),
                    "scenario_ms": block(max(game - 0.30, 0.0005), jitter),
                    "game_ms": block(game, jitter),
                    "render_ms": block(0.18, jitter),
                    "gpu_ms": block(0.21, jitter),
                    "environment": env,
                }

                out_dir = root / args.machine_id / "2026-08-23" / f"tickvstimer_N{n}_{mode}_r{repeat}"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"가짜 결과 생성 완료: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
