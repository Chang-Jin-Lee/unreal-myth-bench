#!/usr/bin/env python3
"""정규화 CSV 에서 마크다운 표와 스케일 곡선 SVG 를 만든다.

외부 라이브러리를 쓰지 않는다. 클론한 사람이 pip 없이 바로 돌릴 수 있어야
재현 가능성이라는 이 프로젝트의 전제가 유지된다.

반복은 프로세스 재시작 단위이므로, 같은 (N, 조건) 의 반복들을 여기서 합친다.
합치는 값은 중앙값이다. 평균은 쓰지 않는다.
"""

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

# 반복 간 중앙값이 이보다 벌어지면 그 조합은 신뢰하지 않는다.
SPREAD_WARN = 0.05


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def group(rows: list[dict], metric: str):
    """(조건, N) -> 반복별 값 목록"""
    buckets = defaultdict(list)
    for row in rows:
        value = row.get(metric)
        if value in (None, ""):
            continue
        buckets[(row["param_extra"], int(row["param_n"]))].append(float(value))
    return buckets


def summarize(buckets):
    """(조건, N) -> (중앙값, 편차비율, 반복수)"""
    out = {}
    for key, values in buckets.items():
        median = statistics.median(values)
        spread = 0.0
        if median > 0 and len(values) > 1:
            spread = (max(values) - min(values)) / median
        out[key] = (median, spread, len(values))
    return out


def markdown_table(summary, metric: str) -> str:
    conditions = sorted({k[0] for k in summary})
    ns = sorted({k[1] for k in summary})

    lines = [f"| 조건 | " + " | ".join(f"N={n:,}" for n in ns) + " |",
             "|---|" + "---|" * len(ns)]
    for cond in conditions:
        cells = []
        for n in ns:
            entry = summary.get((cond, n))
            if entry is None:
                cells.append("—")
                continue
            median, spread, count = entry
            mark = " ⚠" if spread > SPREAD_WARN else ""
            cells.append(f"{median:.3f}{mark}")
        lines.append(f"| `{cond or '기본'}` | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append(f"값은 {metric} 의 중앙값(ms)이고 반복들의 중앙값을 다시 취했습니다. "
                 f"⚠ 는 반복 간 편차가 {SPREAD_WARN:.0%}를 넘은 조합입니다.")
    return "\n".join(lines)


def svg_chart(summary, metric: str, width=720, height=420) -> str:
    """로그 x축 선형 y축 꺾은선. N 이 10배씩 뛰므로 로그가 맞다."""
    conditions = sorted({k[0] for k in summary})
    ns = sorted({k[1] for k in summary})
    if not ns:
        return "<svg xmlns='http://www.w3.org/2000/svg'></svg>"

    pad_l, pad_r, pad_t, pad_b = 64, 140, 24, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    x_min, x_max = math.log10(min(ns)), math.log10(max(ns))
    x_span = (x_max - x_min) or 1.0
    y_max = max(v[0] for v in summary.values()) or 1.0
    y_max *= 1.1

    def px(n):
        return pad_l + (math.log10(n) - x_min) / x_span * plot_w

    def py(value):
        return pad_t + plot_h - (value / y_max) * plot_h

    colors = ["#2f6fdb", "#d1495b", "#3f8f5a", "#b07d2b", "#6a4c93", "#1f7a8c"]
    parts = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"font-family='ui-sans-serif, system-ui, sans-serif' font-size='12'>",
        f"<rect width='{width}' height='{height}' fill='white'/>",
        f"<line x1='{pad_l}' y1='{pad_t + plot_h}' x2='{pad_l + plot_w}' y2='{pad_t + plot_h}' stroke='#333'/>",
        f"<line x1='{pad_l}' y1='{pad_t}' x2='{pad_l}' y2='{pad_t + plot_h}' stroke='#333'/>",
    ]

    for step in range(5):
        value = y_max * step / 4
        y = py(value)
        parts.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{pad_l + plot_w}' y2='{y:.1f}' "
                     f"stroke='#e6e6e6'/>")
        parts.append(f"<text x='{pad_l - 8}' y='{y + 4:.1f}' text-anchor='end' fill='#555'>"
                     f"{value:.2f}</text>")

    for n in ns:
        x = px(n)
        parts.append(f"<text x='{x:.1f}' y='{pad_t + plot_h + 20}' text-anchor='middle' "
                     f"fill='#555'>{n:,}</text>")

    for index, cond in enumerate(conditions):
        color = colors[index % len(colors)]
        points = [(px(n), py(summary[(cond, n)][0])) for n in ns if (cond, n) in summary]
        if not points:
            continue
        path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}"
                        for i, (x, y) in enumerate(points))
        parts.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2'/>")
        for x, y in points:
            parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='3' fill='{color}'/>")
        label_y = pad_t + 16 + index * 18
        parts.append(f"<line x1='{pad_l + plot_w + 12}' y1='{label_y - 4}' "
                     f"x2='{pad_l + plot_w + 32}' y2='{label_y - 4}' stroke='{color}' stroke-width='2'/>")
        parts.append(f"<text x='{pad_l + plot_w + 38}' y='{label_y}' fill='#333'>"
                     f"{cond or '기본'}</text>")

    parts.append(f"<text x='{pad_l + plot_w / 2:.1f}' y='{height - 8}' text-anchor='middle' "
                 f"fill='#333'>N (로그 눈금)</text>")
    parts.append(f"<text x='16' y='{pad_t + 12}' fill='#333'>{metric} (ms)</text>")
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path")
    parser.add_argument("--metric", default="game_ms_median")
    parser.add_argument("--title", default="스케일 곡선")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-svg", required=True)
    args = parser.parse_args()

    rows = load(Path(args.csv_path))
    if not rows:
        print("빈 CSV 다.")
        return 1

    summary = summarize(group(rows, args.metric))
    if not summary:
        print(f"{args.metric} 컬럼에 값이 없다.")
        return 1

    svg_path = Path(args.out_svg)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_chart(summary, args.metric), encoding="utf-8")

    first = rows[0]
    header = (f"# {args.title}\n\n"
              f"머신 `{first['machine_id']}` · 엔진 `{first['engine_version']}` · "
              f"구성 `{first['build_config']}` · RHI `{first['rhi']}` · "
              f"Substrate `{first['substrate']}`\n\n"
              f"워밍업 {first['warmup_frames']} 프레임, 측정 {first['measured_frames']} 프레임.\n\n"
              f"![{args.metric}]({svg_path.name})\n\n")

    md_path = Path(args.out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(header + markdown_table(summary, args.metric) + "\n", encoding="utf-8")

    warned = [k for k, v in summary.items() if v[1] > SPREAD_WARN]
    print(f"{md_path} 와 {svg_path} 생성. 조합 {len(summary)}개.")
    if warned:
        print(f"반복 편차 {SPREAD_WARN:.0%} 초과 {len(warned)}개 — 리포트에 ⚠ 로 표시했다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
