# M1 Tick vs Timer — 게임 스레드 시간

머신 `desktop-13900kf` · CPU `13th Gen Intel(R) Core(TM) i9-13900KF` · 코어 `32` · 코어 고정 `FFFF`
엔진 `5.8.1-56057345+++UE5+Release-5.8` · 구성 `Development` · RHI `D3D12 (SM6)` · Substrate `False`
워밍업 `3.002s` · 측정 `10.001s`

대조군: `mode=disabled;tickgroup=prephysics`. 아래 값은 같은 N 의 대조군을 뺀 순증분(ms)입니다.

| 조건 | N=10 | N=100 | N=1,000 | N=10,000 | 액터 1,000개당 |
|---|---|---|---|---|---|
| `mode=disabled;tickgroup=prephysics` | (0.832) | (0.844) | (0.823) | (0.812) | — |
| `mode=tick;tickgroup=prephysics` | · | 0.031 ⚠ | 0.393 ⚠ | 3.547 | ~0.355 |
| `mode=timer;tickgroup=prephysics` | · | · | 0.046 ⚠ | 0.241 ⚠ | — |

괄호는 대조군의 절대값입니다. `·` 는 순증분이 0.02ms 미만이라 베이스라인 잡음에 묻힌 구간이고, ⚠ 는 반복 간 편차가 순증분의 10%를 넘은 조합입니다. 둘 다 그 지점에서는 측정이 성립하지 않았다는 뜻이지 값이 그렇다는 뜻이 아닙니다.

맨 오른쪽은 신뢰 구간만 써서 원점을 지나는 직선을 맞춘 기울기입니다. 상수 베이스라인이 소거되므로 절대값보다 이쪽이 안정적입니다. `~` 가 붙은 값은 믿을 수 있는 점이 하나뿐이라 직선을 맞춘 게 아니라 그 점 하나에서 나눈 추정치입니다.

히치 비율 중앙값 1.40%, 최대 33.92%.

![game_ms_median](report.svg)
