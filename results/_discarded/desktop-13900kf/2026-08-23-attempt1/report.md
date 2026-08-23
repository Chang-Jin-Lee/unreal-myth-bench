# M1 Tick vs Timer — 게임 스레드 시간

머신 `desktop-13900kf` · 엔진 `5.8.1-56057345+++UE5+Release-5.8` · 구성 `Development` · RHI `D3D12 (SM6)` · Substrate `False`

워밍업 120 프레임, 측정 600 프레임.

![game_ms_median](report.svg)

| 조건 | N=10 | N=100 | N=1,000 | N=10,000 |
|---|---|---|---|---|
| `mode=disabled;tickgroup=prephysics` | 0.810 ⚠ | 0.795 ⚠ | 0.777 | 0.855 ⚠ |
| `mode=tick;tickgroup=prephysics` | 0.825 ⚠ | 0.866 ⚠ | 1.131 ⚠ | 4.622 |
| `mode=timer;tickgroup=prephysics` | 0.763 ⚠ | 0.842 ⚠ | 0.916 ⚠ | 1.114 ⚠ |

값은 game_ms_median 의 중앙값(ms)이고 반복들의 중앙값을 다시 취했습니다. ⚠ 는 반복 간 편차가 5%를 넘은 조합입니다.
