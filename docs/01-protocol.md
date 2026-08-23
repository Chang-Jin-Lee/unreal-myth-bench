# 측정 프로토콜

작성 기준일 2026-08-22 · 대상 엔진 Unreal Engine 5.8

이 문서는 **첫 측정을 시작하기 전에 확정한다.** 조건을 나중에 손보면 앞서 뽑은 데이터를
전부 버려야 한다. 여기 적힌 값을 바꾸려면 그때까지의 결과를 폐기하고 다시 돌린다는 뜻이다.

콘솔 명령과 커맨드라인 플래그는 엔진 버전에 따라 이름이 조금씩 바뀐다.
5.8에서 처음 실행할 때 콘솔 자동완성으로 한 번씩 확인하고, 다른 이름이면 이 문서를 고친다.

---

## 1. 환경 기록

측정값보다 환경 기록이 먼저다. 환경을 모르는 숫자는 쓸모가 없다.

러너가 매 실행마다 `env.json`을 자동으로 남긴다. 수동으로 적지 않는다.

```json
{
  "machine_id": "desktop-5800x",
  "cpu": "AMD Ryzen 7 5800X 8-Core",
  "gpu": "NVIDIA GeForce RTX 3070",
  "ram_gb": 32,
  "os": "Windows 11 26H1 (build ...)",
  "engine_version": "5.8.1-XXXXXXX",
  "build_config": "Development",
  "rhi": "D3D12",
  "scalability": { "view_distance": 3, "shadow": 3, "texture": 3, "effects": 3 },
  "captured_utc": "2026-08-25T04:12:33Z"
}
```

수집 경로는 `FPlatformMisc::GetCPUBrand()`, `FPlatformMisc::GetPrimaryGPUBrand()`,
`FPlatformMemory::GetPhysicalGBRam()`, `FApp::GetBuildConfiguration()`,
`GDynamicRHI->GetName()`을 쓴다.

`machine_id`는 사람이 붙인 짧은 이름이다. 결과 디렉터리 이름이 되므로 머신마다 유일해야 한다.

### 머신이 섞이면 안 되는 이유

같은 시나리오라도 CPU가 다르면 곡선의 절대값이 통째로 이동한다.
서로 다른 머신의 점을 한 그래프에 찍으면 그 그래프는 아무것도 말하지 않는다.
`make_report.py`는 입력에 두 개 이상의 `machine_id`가 섞여 있으면 **실패해야 한다.**
머신 비교가 목적일 때만 전용 리포트를 따로 만든다.

---

## 2. 빌드 구성

| 구성 | 언제 쓰나 | 주의 |
|---|---|---|
| Development | 기본. 프로파일러 계측이 다 살아 있다 | 계측 오버헤드가 있다. 절대값을 실제 출하 성능으로 말하면 안 된다 |
| Shipping | Blueprint vs C++처럼 구성에 민감한 항목 | `stat`과 CSV 상당수가 컴파일 아웃된다. 커스텀 카운터만 남긴다 |
| Test | 필요하면 | Shipping에 가까우면서 일부 계측 유지 |

원칙은 이렇다. **모든 항목을 Development로 한 번 돌리고, 구성에 민감한 항목만 Shipping을
추가로 돌린다.** 두 구성의 숫자는 절대 같은 표에 섞지 않고 컬럼을 나눈다.

M3(Blueprint vs C++)는 반드시 양쪽을 다 잰다. 이 항목은 구성에 따라 결론이 뒤집힐 수 있다.

---

## 3. 실행 조건

### 3.1 고정 CVar

측정 구간에 들어가기 전에 러너가 강제로 적용한다. ini에만 의존하지 않는다.

```
t.MaxFPS 0                  프레임 상한 해제
r.VSync 0                   수직동기 해제
r.ScreenPercentage 100      해상도 스케일 고정
r.DynamicRes.OperationMode 0  동적 해상도 해제
r.DefaultFeature.AutoExposure 0   프레임마다 변하는 후처리 제거
r.DefaultFeature.MotionBlur 0
r.Streaming.PoolSize 0      텍스처 스트리밍 변동 제거 (합성 층 한정)
gc.CollectGarbageEveryFrame 0
sg.ViewDistanceQuality 3     스케일러빌리티 고정. 자동 감지 결과를 덮어쓴다
sg.AntiAliasingQuality 3
sg.PostProcessQuality 3
sg.ShadowQuality 3
sg.TextureQuality 3
sg.EffectsQuality 3
sg.FoliageQuality 3
sg.ShadingQuality 3
```

스케일러빌리티를 명시적으로 박는 이유가 있다. 언리얼은 첫 실행 때 하드웨어 벤치마크를 돌려
결과를 `Saved/Config/.../GameUserSettings.ini`에 쓰는데, `Saved/`는 저장소에 올라가지
않으므로 머신마다 다른 값이 생긴다. 그대로 두면 같은 명령어가 PC마다 다른 렌더 설정으로
돈다. 적용된 값은 `env.json`에 함께 기록한다.

GPU 항목이 아닐 때는 렌더링 부하 자체를 낮춰 신호를 살린다.
GPU를 재는 항목에서는 위의 렌더링 관련 항목을 끄면 안 된다.

### 3.2 커맨드라인 기본형

```
UnrealEditor-Cmd.exe <경로>\MythBench.uproject -game ^
  -bench=TickVsTimer -N=1000 -warmup=120 -frames=600 -repeats=5 ^
  -benchmark -fixedseed ^
  -unattended -nopause -nosound -nosplash ^
  -windowed -resx=1280 -resy=720 ^
  -trace=cpu,frame,counters,bookmark -tracefile=<out>\run.utrace ^
  -log -abslog=<out>\run.log
```

- `-benchmark` — 고정 타임스텝으로 돌려 프레임 간 변동을 줄인다. 실시간이 아니게 되므로 M8처럼 실제 경과 시간이 의미 있는 항목에서는 **빼야 한다**
- `-fixedseed` — 난수 고정
- `-nullrhi` — CPU 전용 항목과 CI에서 추가한다. 렌더링을 통째로 죽이므로 GPU·드로우 항목에는 절대 쓰지 않는다
- 해상도를 고정하는 이유는 창 크기가 드로우 비용에 섞이는 것을 막기 위해서다

### 3.3 항목별로 달라지는 것

| 항목 | -benchmark | -nullrhi | 비고 |
|---|---|---|---|
| M1 Tick/Timer | 사용 | 사용 가능 | Timer는 실제 경과 시간 기준이므로 고정 타임스텝에서의 동작을 문서에 명시 |
| M2 Lyra | 미사용 | 불가 | 실제 플레이 상태를 재는 항목 |
| M3 BP/C++ | 사용 | 사용 가능 | |
| M4 Cast 로드 | 미사용 | 불가 | 로드 시간이 대상 |
| M5 Cast/Implements | 사용 | 사용 가능 | |
| M6 ChildActor | 사용 | 부분 | 메모리 항목은 RHI 필요 |
| M7 GetAllActors | 사용 | 사용 가능 | |
| M8 deadline | **미사용** | 사용 가능 | 고정 타임스텝을 쓰면 항목 자체가 무의미해진다 |
| M9 Paper2D | 미사용 | 불가 | 드로우콜이 대상 |

---

## 4. 워밍업과 반복

| 값 | 기본 | 이유 |
|---|---|---|
| 워밍업 프레임 | 120 | 셰이더 컴파일, 스트리밍, JIT성 초기화가 끝나기를 기다린다 |
| 측정 프레임 | 600 | 10초 남짓. 분포를 볼 만큼은 된다 |
| 반복 횟수 | 5 | 프로세스를 매번 새로 띄운다 |

반복은 **프로세스 재시작 단위**다. 한 프로세스 안에서 다섯 번 재는 것과 다르다.
프로세스를 살려두면 캐시가 데워져 뒤쪽 반복이 유리해진다.

측정 구간 진입 직전과 종료 직후에 강제 GC를 한 번씩 돌리고, 그 프레임은 버린다.

### 통계 처리

- **중앙값과 P95를 기본으로 쓴다.** 평균은 기록하지 않는다. 프레임 시간 분포는 오른쪽으로 긴 꼬리를 가져서 평균이 실제 체감과 어긋난다
- 반복 5회의 중앙값들이 서로 5% 이상 벌어지면 그 실행은 무효로 보고 원인을 찾는다. 백그라운드 프로세스, 발열 스로틀링, 창 포커스가 흔한 원인이다
- 최솟값과 최댓값도 남긴다. 최솟값은 이론 하한을, 최댓값은 히치를 보여준다

---

## 5. 프로파일러 사용법

이 프로젝트의 실질적인 본체다. 도구를 골라 쓰는 순서가 정해져 있고, 순서를 건너뛰면
엉뚱한 곳을 파게 된다.

### 5.1 도구 지도

| 도구 | 무엇을 답하나 | 얻는 것 | 한계 |
|---|---|---|---|
| `stat unit` | 어느 스레드가 병목인가 | Frame / Game / Draw / GPU / RHIT 밀리초 | 프레임 단위. 원인은 안 나온다 |
| `stat game`, `stat engine` | 게임 스레드 어디가 비싼가 | 스탯 그룹별 누적 시간과 호출 수 | 스탯 시스템 자체 오버헤드 |
| CSV Profiler | 시간에 따라 어떻게 변하나 | 프레임별 시계열 CSV | 커스텀 스탯을 심어야 쓸모가 생긴다 |
| Unreal Insights | 정확히 어느 함수인가 | 스코프 트리 타임라인, 카운터, 로드타임, 메모리 | trace 파일이 크다 |
| `ProfileGPU` / `DumpGPU` | GPU 어느 패스인가 | 패스별 GPU 시간 | 단일 프레임 스냅샷 |
| Memory Insights / LLM | 무엇이 메모리를 먹나 | 콜스택별 할당 | 오버헤드가 크다 |
| Reference Viewer / Size Map | 에셋이 무엇을 끌고 오나 | 참조 그래프, 디스크 크기 | 에디터 전용 |

### 5.2 찍는 순서

**1단계 — `stat unit`으로 방향 잡기**

```
stat unit
stat unitgraph
```

Game이 큰지 Draw가 큰지 GPU가 큰지부터 본다. 이걸 건너뛰고 Insights를 켜면
관계없는 스코프를 몇 시간 들여다보게 된다. 이 프로젝트의 항목은 대부분 Game 쪽이지만,
매번 확인하고 리포트에 어느 스레드가 지배적이었는지 적는다.

**2단계 — CSV Profiler로 시계열 확보**

자동화의 기본 산출물이다. 사람이 보는 용도가 아니라 파싱해서 그래프로 만드는 용도다.

```
CsvProfile Start
CsvProfile Stop
```

또는 커맨드라인 `-csvCaptureFrames=600`. 다만 이 플래그는 엔진 시작과 함께 캡처를
시작하므로 워밍업 구간이 섞인다. **러너 코드에서 워밍업이 끝난 뒤 직접 Start를 부르는 쪽이
정확하다.** 결과는 `Saved/Profiling/CSV/`에 떨어진다.

커스텀 스탯을 심는다.

```cpp
CSV_DEFINE_CATEGORY(Bench, true);

// 시나리오 프레임 전체를 감싼다
CSV_SCOPED_TIMING_STAT(Bench, ScenarioFrame);

// 조건을 값으로 남긴다. 나중에 그래프의 x축이 된다
CSV_CUSTOM_STAT(Bench, ActorCount, ActorNum, ECsvCustomStatOp::Set);
```

`ActorCount`처럼 조건 자체를 CSV에 박아두면 파서가 실행 로그를 뒤질 필요가 없다.

**3단계 — Insights로 원인 파고들기**

```
-trace=cpu,frame,counters,bookmark
```

채널은 필요한 것만 켠다. 다 켜면 trace가 수 GB로 커지고 오버헤드가 결과를 오염시킨다.

| 채널 | 언제 |
|---|---|
| `cpu` | 스코프 트리. 거의 항상 |
| `frame` | 프레임 경계. 거의 항상 |
| `counters` | `TRACE_INT_VALUE` 등 커스텀 카운터 |
| `bookmark` | 워밍업 끝, 측정 시작 같은 구간 표시 |
| `gpu` | GPU 항목에서만 |
| `loadtime` | M4 전용 |
| `memalloc` | M6 메모리 항목에서만. 매우 무겁다 |
| `net` | 이 프로젝트에서는 안 쓴다 |

코드에 스코프를 심는다.

```cpp
TRACE_CPUPROFILER_EVENT_SCOPE(MythBench_ScenarioTick);
TRACE_BOOKMARK(TEXT("MeasureStart"));
TRACE_INT_VALUE(TEXT("Bench/ActorCount"), ActorNum);
```

북마크가 특히 중요하다. Insights 타임라인에서 워밍업 구간과 측정 구간을 눈으로 갈라주고,
파서도 이 북마크를 기준으로 자른다.

trace 파일은 `-tracefile=`로 경로를 지정하고, 뷰어는 `UnrealInsights.exe -OpenTraceFile=<경로>`.

**4단계 — GPU는 전용 도구로**

```
ProfileGPU
DumpGPU
```

`stat gpu`로 큰 그림을 보고, 패스별 상세는 `ProfileGPU`가 띄우는 계층 뷰에서 본다.
더 깊이 봐야 하면 RenderDoc이나 PIX, Nsight로 넘어간다.
이 프로젝트에서 GPU가 주인공인 항목은 M9 정도이므로 깊게 갈 일은 많지 않다.

### 5.3 항목별로 무엇을 찍나

| 항목 | 주 도구 | 심을 계측 | 봐야 할 것 |
|---|---|---|---|
| M1 Tick/Timer | CSV + Insights `cpu` | `ScenarioFrame` 스코프, `ActorCount` 카운터 | `stat game`의 Tick 관련 누적 시간, `TickActor`/`TickComponent` 스코프 합계 |
| M2 Lyra | Insights `cpu` | 없음 (엔진 기본 스코프 사용) | `UCharacterMovementComponent::TickComponent`, `APlayerController` Tick, BP Event Tick 스코프의 프레임당 시간 |
| M3 BP/C++ | CSV + Insights `cpu` | 세 구현을 각각 감싼 스코프 | 반복 횟수별 기울기. `stat namedevents`를 켜면 BP 노드 경계가 보인다 |
| M4 Cast 로드 | Insights `loadtime` + Reference Viewer | `TRACE_BOOKMARK`로 로드 시작·끝 | 로드된 패키지 수, 초기 로드 시간, 참조 그래프 노드/엣지 수, Size Map 총 크기 |
| M5 Cast/Implements | CSV | 호출 루프 스코프 | 10^6회 총시간을 호출 수로 나눈 값. 성공/실패 케이스 분리 |
| M6 ChildActor | Insights `cpu` + `memalloc` 또는 LLM | 스폰 구간 스코프 | 스폰 시간, 레벨 로드 시간, 액터당 메모리 증가량 |
| M7 GetAllActors | CSV | 호출 스코프, `ActorCount`와 `CallsPerFrame` 두 카운터 | 두 축의 기울기 비교. 어느 쪽이 지배적인지가 결론이다 |
| M8 deadline | CSV + Insights `frame` | 실행 시각을 카운터로 기록 | 실행 간격 분포, deadline 초과 비율. 프레임 부하를 올려가며 무너지는 지점 |
| M9 Paper2D | `stat unit` + `ProfileGPU` | 없음 | 드로우콜 수, 배칭 여부, GPU 시간 |

### 5.4 보조로 쓰는 것들

- `stat namedevents` — 외부 프로파일러나 Insights에서 스코프 이름을 보이게 한다. 오버헤드가 있으므로 원인 분석할 때만 켜고 최종 수치를 잴 때는 끈다
- `stat dumphitches` — 히치가 의심될 때
- `memreport -full` — 메모리 스냅샷을 텍스트로. M6 보조
- `obj list class=<클래스>` — 오브젝트 수 확인. 시나리오가 의도한 만큼 스폰했는지 검증용
- Reference Viewer — 에디터에서 에셋 우클릭. M4의 주력
- Size Map — 같은 메뉴. 참조를 따라간 총 디스크 크기

### 5.5 흔히 저지르는 실수

- 워밍업 없이 첫 프레임부터 재기. 셰이더 컴파일과 스트리밍이 섞인다
- 에디터 PIE에서 재고 그 숫자를 발표하기. 에디터는 별도 부하가 있다. `-game`으로 독립 실행한다
- `-nullrhi`를 켜놓고 드로우 비용을 논하기
- Insights 채널을 전부 켜고 재기. 계측 오버헤드가 신호보다 커진다
- Development 수치를 출하 성능처럼 말하기
- 평균만 보고 히치를 놓치기
- 창 포커스를 잃은 채로 재기. 백그라운드에서 프레임 제한이 걸린다

---

## 6. 결과 파일

한 번의 실행이 디렉터리 하나를 만든다.

```
results/<machine_id>/<YYYY-MM-DD>/<scenario>_N<n>_r<repeat>/
├─ env.json           환경 정보
├─ run.log            엔진 로그
├─ profile.csv        CSV Profiler 원본
├─ run.utrace         Insights trace (커밋 제외)
└─ summary.json       파서가 만든 정규화 결과
```

`summary.json`의 필드는 00-plan.md의 결과 스키마를 따른다.
`make_report.py`는 `summary.json`만 읽는다. 원본 CSV와 trace는 재검증용으로 남긴다.

`.gitignore`에 `*.utrace`를 넣는다. 나머지는 커밋한다. 원시 데이터가 재현성의 근거다.

---

## 7. 측정 전 체크리스트

한 세션을 시작하기 전에 확인한다.

- [ ] 다른 무거운 프로그램을 닫았다 (브라우저, IDE 빌드, 디스코드)
- [ ] 전원 계획이 고성능이고 노트북이면 어댑터를 꽂았다
- [ ] 엔진 버전이 `env.json`에 기록될 값과 같다
- [ ] 셰이더 컴파일이 끝났다 (한 번 실행해서 DDC를 데워둔다)
- [ ] `machine_id`가 이 머신의 것으로 설정돼 있다
- [ ] 빌드 구성이 의도한 것이다
- [ ] 이전 실행의 `Saved/Profiling/`을 비웠다

측정이 끝나면 반복 5회의 중앙값 편차를 먼저 확인하고, 5%를 넘으면 원인을 찾은 뒤 다시 돌린다.

---

## 8. 리포트에 반드시 적을 것

숫자만 있는 리포트는 신뢰받지 못한다. 각 항목 문서에 다음을 같이 적는다.

- 어느 머신, 어느 빌드 구성, 어느 엔진 버전
- 워밍업·측정·반복 값 (기본값과 다르면 이유도)
- `-benchmark`와 `-nullrhi` 사용 여부
- 재현 명령어 전문
- 어느 스레드가 지배적이었는지
- **측정하지 못한 것과 그 이유.** 이걸 적는 리포트가 안 적는 리포트보다 신뢰도가 높다
