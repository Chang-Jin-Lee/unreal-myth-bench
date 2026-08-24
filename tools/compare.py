#!/usr/bin/env python3
"""조건 사이 A/B 비교표. CPU 시간, GPU 시간, 프레임레이트를 한 화면에 놓는다.

중앙값 하나로는 판단할 수 없다. 1차·2차 측정에서 Timer 는 중앙값 순증분이
Tick 의 1/15 였지만 P95 는 오히려 더 컸다. 주기마다 몰려서 터지기 때문이다.
그래서 중앙값과 P95 의 순위가 뒤집히면 여기서 잡아 표시한다.

프로파일이 둘이다.
  cpu  : -nullrhi. 게임 스레드 신호를 렌더에서 분리해서 본다
  full : 실제 RHI. GPU 시간과 프레임레이트가 의미를 갖는다
"""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

METRICS = [
    ("game_ms_median", "CPU 중앙", "ms"),
    ("game_ms_p95",    "CPU P95",  "ms"),
    ("frame_ms_median","프레임 중앙", "ms"),
    ("frame_ms_p95",   "프레임 P95", "ms"),
    ("gpu_ms_median",  "GPU 중앙", "ms"),
    ("average_fps",    "평균 fps", ""),
    ("hitch_ratio",    "히치", "%"),
]


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def median_of(rows, key):
    vals = [float(r[key]) for r in rows if r.get(key) not in (None, "")]
    return statistics.median(vals) if vals else None


def build(rows, n: int, profile: str):
    """조건 -> 지표 중앙값. 반복은 중앙값으로 합친다."""
    grouped = defaultdict(list)
    for row in rows:
        if int(row["param_n"]) != n:
            continue
        if row.get("profile", "full") != profile:
            continue
        grouped[row["param_extra"]].append(row)

    table = {}
    for cond, group in grouped.items():
        table[cond] = {key: median_of(group, key) for key, _, _ in METRICS}
        table[cond]["_runs"] = len(group)
    return table


def rank(table, key):
    """값이 있는 조건만 작은 순으로. 순위 비교용."""
    have = [(cond, vals[key]) for cond, vals in table.items() if vals.get(key) is not None]
    return [cond for cond, _ in sorted(have, key=lambda kv: kv[1])]


def render(table, n, profile) -> str:
    if not table:
        return f"\n### N={n:,} · {profile}\n\n해당 조합의 데이터가 없습니다.\n"

    conds = sorted(table)
    lines = [f"\n### N={n:,} · `{profile}` 프로파일\n",
             "| 지표 | " + " | ".join(f"`{c}`" for c in conds) + " |",
             "|---|" + "---|" * len(conds)]

    for key, label, unit in METRICS:
        if profile == "cpu" and key in ("gpu_ms_median", "average_fps"):
            continue  # -nullrhi 에서는 의미가 없다
        cells = []
        for cond in conds:
            value = table[cond].get(key)
            if value is None:
                cells.append("—")
            elif unit == "%":
                cells.append(f"{value*100:.1f}%")
            elif key == "average_fps":
                cells.append(f"{value:,.0f}")
            else:
                cells.append(f"{value:.3f}")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines.append(f"| 반복 수 | " + " | ".join(str(table[c]["_runs"]) for c in conds) + " |")

    # 중앙값과 P95 의 순위가 다르면 그게 결론을 뒤집는다.
    notes = []
    for base, tail, name in (("game_ms_median", "game_ms_p95", "CPU"),
                             ("frame_ms_median", "frame_ms_p95", "프레임")):
        med_rank, p95_rank = rank(table, base), rank(table, tail)
        if len(med_rank) > 1 and med_rank != p95_rank:
            notes.append(
                f"**{name} 중앙값과 P95 의 순위가 다릅니다.** "
                f"중앙값 기준 `{' < '.join(med_rank)}`, "
                f"P95 기준 `{' < '.join(p95_rank)}`. "
                f"중앙값만 보고 고르면 프레임 품질에서 손해를 봅니다.")

    for cond, vals in table.items():
        hitch = vals.get("hitch_ratio")
        if hitch is not None and hitch > 0.05:
            notes.append(f"`{cond}` 히치 {hitch*100:.1f}%. 값을 인용하기 전에 원인을 확인합니다.")

    if notes:
        lines.append("")
        lines += [f"- {note}" for note in notes]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path")
    parser.add_argument("--n", default="", help="쉼표로 구분. 비우면 있는 N 전부")
    parser.add_argument("--profile", default="", help="cpu / full. 비우면 둘 다")
    parser.add_argument("--title", default="A/B 비교")
    parser.add_argument("-o", "--output", default="")
    args = parser.parse_args()

    rows = load(Path(args.csv_path))
    if not rows:
        print("빈 CSV 다.")
        return 1

    ns = ([int(x) for x in args.n.split(",") if x.strip()] if args.n
          else sorted({int(r["param_n"]) for r in rows}))
    profiles = ([args.profile] if args.profile
                else sorted({r.get("profile", "full") for r in rows}))

    first = rows[0]
    out = [f"# {args.title}\n",
           f"머신 `{first['machine_id']}` · CPU `{first['cpu']}` · "
           f"코어 고정 `{first.get('affinity') or '기록 없음'}`",
           f"엔진 `{first['engine_version']}` · 구성 `{first['build_config']}`",
           "",
           "`cpu` 프로파일은 `-nullrhi` 라 GPU 시간과 fps 가 빠집니다. "
           "그 둘은 `full` 프로파일에서 봅니다."]

    for profile in profiles:
        for n in ns:
            out.append(render(build(rows, n, profile), n, profile))

    text = "\n".join(out)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"{path} 생성")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
