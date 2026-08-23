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
  -bench=tickvstimer -N=1000 -mode=tick -tickgroup=prephysics ^
  -warmupsec=3 -measuresec=10 -repeat=0 ^
  -machineid=desktop-13900kf -out=<out> ^
  -benchmark -fixedseed ^
  -unattended -nopause -nosound -nosplash ^
  -windowed -resx=1280 -resy=720 ^
  -trace=cpu,frame,counters,bookmark -tracefile=<out>\run.utrace ^
  -log -abslog=<out>\run.log
```

`tools/run_bench.py` 가 이 명령을 만들어 준다. 손으로 칠 일은 디버깅할 때뿐이다.

- `-warmupsec` / `-measuresec` — **프레임 수가 아니라 시간으로 자른다.** 프레임 시간
  자체가 측정 대상이라 프레임 수로 자르면 조건마다 측정 창 길이가 달라진다. 1차 측정에서
  실제로 이 문제가 났다. 자세한 경위는 `docs/10-synthetic.md` 에 있다
- `-benchmark` — 고정 타임스텝. 실제 경과 시간이 의미 있는 항목에서는 **빼야 한다**
- `-fixedseed` — 난수 고정
- `-nullrhi` — 게임 스레드만 보는 항목에서 쓴다. `run_bench.py` 가 `--rhi auto` 일 때
  자동으로 붙인다. 렌더링을 통째로 죽이므로 GPU·드로우 항목에는 절대 쓰지 않는다
- `-affinity=` — 러너가 기록만 한다. 실제 코어 고정은 런처가 `start /affinity` 로 건다

### 3.4 하이브리드 CPU 는 코어를 고정한다

P코어와 E코어가 섞인 CPU 에서는 게임 스레드가 두 종류의 코어를 오가면서 프레임 시간이
크게 흔들린다. 측정 전에 P코어에만 묶는다.

```
python tools/run_bench.py ... --affinity FFFF
```

마스크는 논리 CPU 비트맵이다. 13900KF 는 P코어 8개가 하이퍼스레딩으로 논리 16개(0–15)를
차지하므로 `FFFF` 다. CPU 가 다르면 작업 관리자나 `Get-CimInstance Win32_Processor` 로
P코어 수를 먼저 확인한다. 적용한 마스크는 `env.json` 의 `affinity` 에 남는다.

### 3.3 항목별로 달라지는 것

| 항목 | -benchmark | -nullrhi | 비고 |
|---|---|---|---|
| M1 Tick/Timer | 사용 | **기본 사용** | Timer는 실제 경과 시간 기준이므로 고정 타임스텝에서의 동작을 문서에 명시 |
| M2 Lyra | 미사용 | 불가 | 실제 플레이 상태를 재는 항목 |
| M3 BP/C++ | 사용 | 기본 사용 | |
| M4 Cast 로드 | 미사용 | 불가 | 로드 시간이 대상 |
| M5 Cast/Implements | 사용 | 기본 사용 | |
| M6 ChildActor | 사용 | 부분 | 메모리 항목은 RHI 필요 |
| M7 GetAllActors | 사용 | 기본 사용 | |
| M8 deadline | **미사용** | 사용 가능 | 고정 타임스텝을 쓰면 항목 자체가 무의미해진다 |
| M9 Paper2D | 미사용 | 불가 | 드로우콜이 대상 |

---

## 4. 워밍업과 반복

| 값 | 기본 | 이유 |
|---|---|---|
| 워밍업 | **3초** | 셰이더 컴파일, 스트리밍, CPU 부스트 클럭이 자리 잡기를 기다린다 |
| 측정 | **10초** | 분포를 볼 만큼은 되고, 발열로 클럭이 내려가기 전에 끝난다 |
| 반복 | 5회 | 프로세스를 매번 새로 띄운다 |

**프레임 수가 아니라 시간으로 자른다.** 1차 측정에서 120프레임 / 600프레임으로 잡았다가
빈 맵이 780fps 로 돌아 워밍업 0.15초, 측정 0.9초가 됐다. 조건마다 프레임 시간이 다르니
측정 창 길이도 조건마다 달라졌고, 클럭이 안정되기 전에 끝나서 같은 조건의 반복끼리도
값이 15% 씩 벌어졌다.

반복은 **프로세스 재시작 단위**다. 한 프로세스 안에서 다섯 번 재는 것과 다르다.
프로세스를 살려두면 캐시가 데워져 뒤쪽 반복이 유리해진다.

측정 구간 진입 직전에 강제 GC 를 한 번 돌린다. 러너가 알아서 한다.

### 통계 처리

- **중앙값과 P95 를 쓴다. 평균은 기록하지 않는다.** 프레임 시간 분포는 오른쪽으로 긴
  꼬리를 가져서 평균이 실제 체감과 어긋난다
- 최솟값과 최댓값도 남긴다. 최솟값은 이론 하한을, 최댓값은 히치를 보여준다
- **절대값이 아니라 대조군을 뺀 순증분을 보고한다.** 빈 맵에서도 게임 스레드 베이스라인이
  0.8ms 쯤 나오는데 액터 10개의 Tick 비용은 0.004ms 다. 절대값을 그대로 실으면 베이스라인의
  잡음을 측정값이라고 발표하게 된다
- 반복 간 편차 판정도 **순증분 대비**로 한다. 절대 편차로 재면 신호가 작을수록 무조건
  걸려서 기준이 거꾸로 작동한다. 1차 측정에서 편차 0.199ms 인 조합은 통과하고
  0.068ms 인 조합이 경고를 받았다
- 여러 N 에서 신뢰할 수 있는 점이 둘 이상이면 **기울기**를 함께 낸다. 상수 베이스라인이
  소거되므로 절대값보다 안정적이다

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

## 6. 무엇을 남기는가

### 6.1 러너가 자동으로 남기는 것

한 번의 실행이 디렉터리 하나를 만든다.

| 파일 | 내용 | 커밋 |
|---|---|---|
| `env.json` | 머신·CPU·코어 수·코어 고정·GPU·RAM·OS·엔진·빌드 구성·RHI·Substrate·스케일러빌리티 | 한다 |
| `summary.json` | 조건, 측정 시간과 프레임 수, 평균 fps, 히치 비율, 렌더 바운드 여부, 품질 경고, 지표별 중앙값·P95·최소·최대 | 한다 |
| `frames.csv` | 프레임별 원본 5열. **정렬 전 순서 그대로** 라 히치가 언제 났는지 보인다 | 한다 |
| `run.log` | 엔진 로그 전문 | 한다 |
| `run.utrace` | Insights trace | **안 한다** (크다) |

`frames.csv` 를 순서대로 남기는 게 중요하다. 중앙값만 있으면 "런 중간에 값이 계속 올라갔다"
같은 것을 나중에 확인할 수 없다. 1차 측정의 드리프트도 이 파일 덕분에 찾았다.

### 6.2 `run.log` 에서 볼 줄

러너가 태그를 붙여 찍는다. `run.log` 만 열어도 어디서 무엇을 어떻게 쟀는지 나와야 한다.

```
[env]     machine=... cpu=... cores=32 affinity=FFFF gpu=... engine=5.8.1-... config=Development rhi=D3D12 substrate=off
[out]     결과 디렉터리
[spec]    scenario=tickvstimer N=1000 mode=tick tickgroup=prephysics warmup=3.0s measure=10.0s repeat=0
[phase]   워밍업 3.01초 종료. 측정 10.0초 시작.
[phase]   측정 종료. 7841 프레임 / 10.00초 / 평균 784 fps
[stat]    game median=... p95=... | frame median=... p95=... | render median=... | gpu median=...
[quality] 경고 없음
```

`[quality]` 가 핵심이다. 러너가 스스로 네 가지를 판정한다.

| 경고 | 뜻 | 대응 |
|---|---|---|
| 측정 창이 5초 미만 | 클럭이 안정되기 전에 끝났다 | `-measuresec` 를 늘린다 |
| 히치 1% 초과 | 프레임이 규칙적으로 튄다 | 백그라운드 프로세스, 코어 고정을 확인한다 |
| 렌더 스레드 > 게임 스레드 | 프레임이 렌더에 묶여 있다 | CPU 항목이면 `-nullrhi` 로 돌린다 |
| 샘플 300 프레임 미만 | 분포를 보기에 부족하다 | 측정 시간을 늘린다 |

경고가 하나라도 뜬 실행은 리포트에 쓰기 전에 원인을 찾는다. `parse_results.py` 가
집계할 때 경고를 다시 한 번 올려 준다. 조용히 넘어가지 않게 하려는 것이다.

### 6.3 사람이 손으로 남기는 것

러너가 알 수 없는 것들이 있다. 측정 세션마다
`results/<machine>/<date>/session.md` 를 쓴다. 서식은 `docs/templates/session-log.md`
를 복사해서 쓴다.

여기에 적을 것은 러너가 볼 수 없는 것들이다. 어떤 프로그램을 닫았고 무엇을 켜둔 채였는지,
전원 계획이 무엇이었는지, 노트북이면 어댑터를 꽂았는지, 중간에 자리를 비웠는지, 실행 도중
눈에 띈 이상한 점이 있었는지. 나중에 값이 이상할 때 이 기록이 유일한 단서가 된다.

### 6.4 실패했을 때

성공한 실행만 남기면 안 된다. 실패도 기록이다.

- 엔진이 죽었으면 `run.log` 와 `Saved/Crashes/` 의 크래시 리포트를 세션 디렉터리로 옮긴다
- `run_bench.py` 가 잡은 표준 오류는 `stderr.txt` 로 자동으로 떨어진다
- 조건을 바꿔 다시 돌렸다면 **바꾼 것과 이유**를 세션 로그에 적는다. 이게 없으면
  나중에 두 결과의 차이를 설명할 수 없다

### 6.5 폐기할 때

프로토콜을 바꾸면 그 이전 결과는 폐기 대상이다. 그런데 **지우지는 않는다.**
결과 디렉터리를 그대로 두고 세션 로그와 리포트 문서에 왜 폐기했는지 적는다.
"1차 측정은 워밍업이 0.15초여서 못 쓴다"는 기록이 남아 있어야, 나중에 같은 실수를
반복하지 않고 리포트를 읽는 사람도 판단 과정을 따라올 수 있다.

## 7. 측정 전 체크리스트

한 세션을 시작하기 전에 확인한다.

- [ ] 다른 무거운 프로그램을 닫았다 (브라우저, IDE 빌드, 디스코드)
- [ ] 전원 계획이 고성능이고 노트북이면 어댑터를 꽂았다
- [ ] 하이브리드 CPU 면 `--affinity` 로 P코어에 묶었다
- [ ] 엔진 버전이 `env.json` 에 기록될 값과 같다
- [ ] 셰이더 컴파일이 끝났다 (한 번 실행해서 DDC 를 데워둔다)
- [ ] `machine_id` 가 이 머신의 것이다
- [ ] 빌드 구성이 의도한 것이다
- [ ] 이전 실행의 `Saved/Profiling/` 을 비웠다
- [ ] 세션 로그 파일을 만들어 뒀다

측정이 끝나면 `[quality]` 경고부터 확인한다. 경고가 없어야 다음으로 넘어간다.

## 8. 리포트에 반드시 적을 것

숫자만 있는 리포트는 신뢰받지 못한다. 각 항목 문서에 다음을 같이 적는다.
`make_report.py` 가 앞부분을 자동으로 채워 준다.

- 어느 머신, 어느 CPU, 코어 고정 여부, 어느 빌드 구성, 어느 엔진 버전
- 워밍업과 측정 시간, 반복 횟수
- `-benchmark` 와 `-nullrhi` 사용 여부
- 재현 명령어 전문
- 어느 스레드가 지배적이었는지
- 대조군과 순증분. 절대값만 싣지 않는다
- 신뢰할 수 없다고 판정한 구간과 그 이유
- **측정하지 못한 것과 그 이유.** 이걸 적는 리포트가 안 적는 리포트보다 신뢰도가 높다
