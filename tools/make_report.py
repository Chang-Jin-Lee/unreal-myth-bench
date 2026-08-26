#!/usr/bin/env python3
"""정규화 CSV 에서 마크다운 표와 스케일 곡선 SVG 를 만든다.

외부 라이브러리를 쓰지 않는다. 클론한 사람이 pip 없이 바로 돌릴 수 있어야
재현 가능성이라는 이 프로젝트의 전제가 유지된다.

핵심은 절대값이 아니라 **대조군을 뺀 순증분**이다. 빈 맵에서도 게임 스레드
베이스라인이 0.8ms 쯤 나오는데, N=10 액터의 비용은 0.004ms 수준이다. 절대값을
그대로 실으면 베이스라인의 잡음을 측정값이라고 발표하게 된다.
"""

import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path

# 순증분 대비 반복 편차가 이보다 크면 그 조합은 신뢰하지 않는다.
# 절대 편차로 재면 신호가 작을수록 무조건 걸려서 기준이 거꾸로 작동한다.
SPREAD_WARN = 0.10
# 순증분이 이보다 작으면 베이스라인 잡음에 묻힌 것으로 본다 (ms).
# 스윕에서 노이즈 바닥을 잴 수 있으면 그쪽이 이긴다. 이 상수는 대조군이
# 없거나 반복이 1회뿐이라 바닥을 못 재는 경우의 하한일 뿐이다.
SIGNAL_FLOOR = 0.02


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def collect(rows: list[dict], metric: str):
    """(조건, N) -> 반복별 값 목록"""
    buckets = defaultdict(list)
    for row in rows:
        value = row.get(metric)
        if value in (None, ""):
            continue
        buckets[(row["param_extra"], int(row["param_n"]))].append(float(value))
    return buckets


def pick_baseline(conditions, explicit: str) -> str | None:
    if explicit:
        return explicit
    for cond in conditions:
        if "disabled" in cond or "none" in cond:
            return cond
    return None


def noise_floor(buckets, baseline: str | None) -> float:
    """이 스윕의 측정 하한. 대조군 전체 실행의 산포로 잰다.

    대조군은 N 과 무관하게 액터당 작업이 0 이므로, 그 값들이 흩어지는 폭이
    곧 이 머신에서 이 조건으로 잴 수 있는 한계다. 그보다 좁은 차이를 요구하는
    기준은 측정이 나빠서가 아니라 기준이 잴 수 없는 정밀도를 요구해서 걸린다.

    상대 기준만 쓰면 순증분이 작을수록 허용 폭이 무한히 좁아진다. 실제로
    2026-08-23 스윕에서 순증분 0.393ms(노이즈의 4.7배로 분명한 신호)가
    허용폭 0.039ms 를 넘겼다는 이유로 걸렸는데, 그 0.086ms 산포는 사실상
    노이즈 바닥 그 자체였다.
    """
    if not baseline:
        return 0.0
    values = [v for (cond, _), vals in buckets.items() if cond == baseline for v in vals]
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)


def analyse(buckets, baseline: str | None):
    """(조건, N) -> dict(raw, spread, net, count)"""
    noise = noise_floor(buckets, baseline)
    base = {}
    if baseline:
        for (cond, n), values in buckets.items():
            if cond == baseline:
                base[n] = statistics.median(values)

    out = {}
    for (cond, n), values in buckets.items():
        raw = statistics.median(values)
        spread = (max(values) - min(values)) if len(values) > 1 else 0.0
        net = raw - base.get(n, 0.0) if baseline else raw
        out[(cond, n)] = {
            "raw": raw, "spread": spread, "net": net, "count": len(values),
            "is_baseline": cond == baseline, "noise": noise,
        }
    return out


def slope_per_1k(points: list[tuple[int, float]]):
    """원점을 지나는 최소제곱 기울기. 상수 베이스라인은 이미 빠졌다고 본다.

    믿을 수 있는 점이 하나뿐이면 기울기가 아니라 그 점 하나의 추정치다.
    구분해서 돌려준다.
    """
    usable = [(n, v) for n, v in points if n > 0]
    if not usable:
        return None, False
    if len(usable) == 1:
        n, v = usable[0]
        return v / n * 1000.0, False
    num = sum(n * v for n, v in usable)
    den = sum(n * n for n, _ in usable)
    if den == 0:
        return None, False
    return num / den * 1000.0, True


def signal_floor(entry) -> float:
    """이 조합에서 신호로 인정할 최소 순증분.

    노이즈 바닥을 잴 수 있으면 그것이 기준이다. 바닥보다 작은 차이는
    반복을 더 돌려도 잡음과 구별되지 않는다. SIGNAL_FLOOR 는 대조군이
    없어 바닥을 못 잰 경우의 대비책이다.
    """
    return max(entry.get("noise", 0.0), SIGNAL_FLOOR)


def verdict(entry) -> str:
    if entry["is_baseline"]:
        return "대조군"
    if entry["net"] < signal_floor(entry):
        return "신호 없음"
    # 허용 폭은 상대 기준과 노이즈 바닥 중 넓은 쪽이다. 상대 기준만 쓰면
    # 신호가 작을수록 이 장비로 도달 불가능한 정밀도를 요구하게 된다.
    tolerance = max(SPREAD_WARN * entry["net"], entry.get("noise", 0.0))
    if entry["spread"] > tolerance:
        return "편차 큼"
    return "OK"


def markdown(rows, analysis, metric, baseline):
    noise = next((e["noise"] for e in analysis.values()), 0.0)
    base_n = sum(e["count"] for k, e in analysis.items() if e["is_baseline"])
    conditions = sorted({k[0] for k in analysis})
    ns = sorted({k[1] for k in analysis})
    first = rows[0]
    def field(key, suffix=""):
        value = first.get(key, "")
        return f"{value}{suffix}" if value not in (None, "") else "기록 없음"

    lines = [
        f"머신 `{field('machine_id')}` · CPU `{field('cpu')}` · "
        f"코어 `{field('core_count')}` · 코어 고정 `{field('affinity')}`",
        f"엔진 `{field('engine_version')}` · 구성 `{field('build_config')}` · "
        f"RHI `{field('rhi')}` · Substrate `{field('substrate')}`",
        f"워밍업 `{field('warmup_seconds', 's')}` · 측정 `{field('measured_seconds', 's')}`",
        "",
        f"대조군: `{baseline or '없음'}`. 아래 값은 같은 N 의 대조군을 뺀 순증분(ms)입니다.",
        "",
        "| 조건 | " + " | ".join(f"N={n:,}" for n in ns) + " | 액터 1,000개당 |",
        "|---|" + "---|" * (len(ns) + 1),
    ]

    for cond in conditions:
        cells, points = [], []
        for n in ns:
            entry = analysis.get((cond, n))
            if entry is None:
                cells.append("—")
                continue
            state = verdict(entry)
            if entry["is_baseline"]:
                cells.append(f"({entry['raw']:.3f})")
            elif state == "신호 없음":
                cells.append("·")
            elif state == "편차 큼":
                cells.append(f"{entry['net']:.3f} ⚠")
            else:
                cells.append(f"{entry['net']:.3f}")
                points.append((n, entry["net"]))
        per_1k, is_fit = slope_per_1k(points)
        if per_1k is None:
            cells.append("—")
        elif is_fit:
            cells.append(f"**{per_1k:.3f}**")
        else:
            cells.append(f"~{per_1k:.3f}")
        lines.append(f"| `{cond}` | " + " | ".join(cells) + " |")

    lines += [
        "",
        f"괄호는 대조군의 절대값입니다. `·` 는 순증분이 노이즈 바닥보다 작아 "
        f"베이스라인 잡음에 묻힌 구간이고, ⚠ 는 반복 간 편차가 허용 폭을 넘은 "
        f"조합입니다. 둘 다 그 지점에서는 측정이 성립하지 않았다는 뜻이지 값이 "
        f"그렇다는 뜻이 아닙니다.",
        "",
        f"허용 폭은 `max(순증분의 {SPREAD_WARN:.0%}, 노이즈 바닥)` 입니다. "
        f"이 스윕의 노이즈 바닥은 **{noise:.4f} ms** 로, 대조군 {base_n}회 실행의 "
        f"산포에서 잰 값입니다. 대조군은 N 과 무관하게 액터당 작업이 0 이므로 "
        f"그 흩어짐이 곧 이 머신의 측정 하한입니다. 상대 기준만 쓰면 신호가 작을수록 "
        f"이 장비로 도달할 수 없는 정밀도를 요구하게 되어, 분명한 신호까지 "
        f"측정 실패로 표시됩니다.",
        "",
        f"맨 오른쪽은 신뢰 구간만 써서 원점을 지나는 직선을 맞춘 기울기입니다. "
        f"상수 베이스라인이 소거되므로 절대값보다 이쪽이 안정적입니다. "
        f"`~` 가 붙은 값은 믿을 수 있는 점이 하나뿐이라 직선을 맞춘 게 아니라 "
        f"그 점 하나에서 나눈 추정치입니다.",
    ]

    hitch = [float(r["hitch_ratio"]) for r in rows if r.get("hitch_ratio") not in (None, "")]
    if hitch:
        lines += ["", f"히치 비율 중앙값 {statistics.median(hitch):.2%}, "
                      f"최대 {max(hitch):.2%}."]
    return "\n".join(lines)


def svg_chart(analysis, metric, width=760, height=430) -> str:
    series = defaultdict(list)
    for (cond, n), entry in analysis.items():
        if entry["is_baseline"] or entry["net"] < signal_floor(entry):
            continue
        series[cond].append((n, entry["net"]))
    for cond in series:
        series[cond].sort()

    if not series:
        return ("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='60'>"
                "<text x='8' y='34'>측정 가능한 신호가 없습니다</text></svg>")

    ns = sorted({n for pts in series.values() for n, _ in pts})
    pad_l, pad_r, pad_t, pad_b = 70, 150, 26, 50
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    x_min, x_max = math.log10(min(ns)), math.log10(max(ns))
    x_span = (x_max - x_min) or 1.0
    y_max = max(v for pts in series.values() for _, v in pts) * 1.12 or 1.0

    px = lambda n: pad_l + (math.log10(n) - x_min) / x_span * plot_w
    py = lambda v: pad_t + plot_h - (v / y_max) * plot_h

    colors = ["#2f6fdb", "#d1495b", "#3f8f5a", "#b07d2b", "#6a4c93", "#1f7a8c"]
    out = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
           f"font-family='ui-sans-serif, system-ui, sans-serif' font-size='12'>",
           f"<rect width='{width}' height='{height}' fill='white'/>",
           f"<line x1='{pad_l}' y1='{pad_t+plot_h}' x2='{pad_l+plot_w}' y2='{pad_t+plot_h}' stroke='#333'/>",
           f"<line x1='{pad_l}' y1='{pad_t}' x2='{pad_l}' y2='{pad_t+plot_h}' stroke='#333'/>"]

    for step in range(5):
        value = y_max * step / 4
        y = py(value)
        out.append(f"<line x1='{pad_l}' y1='{y:.1f}' x2='{pad_l+plot_w}' y2='{y:.1f}' stroke='#e6e6e6'/>")
        out.append(f"<text x='{pad_l-8}' y='{y+4:.1f}' text-anchor='end' fill='#555'>{value:.2f}</text>")
    for n in ns:
        out.append(f"<text x='{px(n):.1f}' y='{pad_t+plot_h+20}' text-anchor='middle' fill='#555'>{n:,}</text>")

    for index, (cond, pts) in enumerate(sorted(series.items())):
        color = colors[index % len(colors)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{px(n):.1f},{py(v):.1f}"
                        for i, (n, v) in enumerate(pts))
        out.append(f"<path d='{path}' fill='none' stroke='{color}' stroke-width='2'/>")
        for n, v in pts:
            out.append(f"<circle cx='{px(n):.1f}' cy='{py(v):.1f}' r='3' fill='{color}'/>")
        label_y = pad_t + 16 + index * 18
        out.append(f"<line x1='{pad_l+plot_w+12}' y1='{label_y-4}' x2='{pad_l+plot_w+32}' "
                   f"y2='{label_y-4}' stroke='{color}' stroke-width='2'/>")
        out.append(f"<text x='{pad_l+plot_w+38}' y='{label_y}' fill='#333'>{cond}</text>")

    out.append(f"<text x='{pad_l+plot_w/2:.1f}' y='{height-8}' text-anchor='middle' fill='#333'>N (로그 눈금)</text>")
    out.append(f"<text x='14' y='{pad_t+12}' fill='#333'>{metric} 순증분 (ms)</text>")
    out.append("</svg>")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path")
    parser.add_argument("--metric", default="game_ms_median")
    parser.add_argument("--title", default="스케일 곡선")
    parser.add_argument("--baseline", default="",
                        help="대조군 조건 문자열. 비우면 disabled 를 자동으로 찾는다")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-svg", required=True)
    args = parser.parse_args()

    rows = load(Path(args.csv_path))
    if not rows:
        print("빈 CSV 다.")
        return 1

    buckets = collect(rows, args.metric)
    if not buckets:
        print(f"{args.metric} 컬럼에 값이 없다.")
        return 1

    baseline = pick_baseline({k[0] for k in buckets}, args.baseline)
    if baseline is None:
        print("대조군을 찾지 못했다. --baseline 으로 지정하면 순증분을 계산한다.")
    analysis = analyse(buckets, baseline)

    svg_path = Path(args.out_svg)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_chart(analysis, args.metric), encoding="utf-8")

    md_path = Path(args.out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    body = (f"# {args.title}\n\n"
            + markdown(rows, analysis, args.metric, baseline)
            + f"\n\n![{args.metric}]({svg_path.name})\n")
    md_path.write_text(body, encoding="utf-8")

    states = defaultdict(int)
    for entry in analysis.values():
        states[verdict(entry)] += 1
    print(f"{md_path} 와 {svg_path} 생성.")
    print("  " + " · ".join(f"{k} {v}" for k, v in sorted(states.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
