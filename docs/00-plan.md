# unreal-myth-bench — 기획 문서

작성 기준일 2026-08-22 · 대상 엔진 Unreal Engine 5.8

---

## 1. 무엇을 만드는가

언리얼에서 오래 돌아다니는 성능 통설 아홉 개를 실측으로 검증하는 벤치마크 하네스다.
산출물은 데모 장면이 아니라 **다른 사람이 클론해서 같은 숫자를 뽑을 수 있는 리포트**다.

측정 항목은 2026 언리얼 페스트 "언리얼 엔진의 모범 사례에 대한 오해와 진실" 트랙에서
직접 물어본 질문을 그대로 옮겼다. 강연에서 들은 결론을 받아 적는 대신 각 주장이
**어떤 조건에서 참이 되는지**를 곡선으로 남기는 것이 이 프로젝트의 목적이다.

### 왜 만드는가

포트폴리오 관점에서 비어 있는 칸이 "최적화·프로파일링 근거"다.
게임을 하나 더 만드는 것보다 계측 능력을 보여주는 쪽이 그 칸을 정확히 채운다.
면접에서 꺼낼 수 있는 이야기가 항목 수만큼 생기는 것도 부수 효과다.

### 무엇을 만들지 않는가

- 게임플레이. 캐릭터도 적도 UI도 만들지 않는다
- 에셋. 맵 하나와 큐브 몇 개면 끝난다. 레포가 가벼워야 클론이 쉽다
- 결론 선언. "Tick은 느리다" 같은 문장을 먼저 정해두고 그걸 뒷받침하는 수치를 찾으면 프로젝트가 죽는다

---

## 2. 세 개의 층

측정 대상에 따라 다루는 방식이 다르다. 레포는 하나지만 안에서 갈린다.

| 층 | 대상 | 레포에 들어가는 것 |
|---|---|---|
| 합성 | 이 프로젝트가 직접 스폰한 액터·오브젝트 | 코드 전부 + 결과 CSV |
| 기준점 | Lyra Starter Game | 재현 절차와 숫자만. **코드·에셋은 넣지 않는다** |
| 프로덕션 | Metropia_UE 등 실제 프로젝트 | 사례 문서와 그래프만. **코드는 넣지 않는다** |

Lyra와 프로덕션 프로젝트의 소스를 공개 레포에 복사하면 라이선스와 소유권 문제가 생긴다.
프로덕션에서 발견한 패턴을 코드로 보여줘야 한다면 **최소 형태로 합성 층에 다시 구현**한다.
그래야 공개 레포가 자체 완결되고 프로덕션 사례는 근거로만 붙는다.

---

## 3. 측정 항목

공통 스윕 축은 `N = 10 / 100 / 1,000 / 10,000`이다. 항목에 따라 축이 추가된다.
단일 숫자가 아니라 곡선을 남기는 것이 핵심이다. 통설은 대부분 특정 구간에서만 참이다.

### M1. Tick vs Timer vs 이벤트 구동

- **통설** — Tick을 쓰지 마라
- **가설** — 비용은 Tick이라는 기능이 아니라 등록된 Tick 함수 수와 그 안의 작업량에 비례한다. Tick Group은 비용이 아니라 프레임 안에서의 실행 시점을 정한다
- **방법** — 액터 N개를 스폰하고 세 조건으로 돌린다. 빈 `TickComponent` / `TimerManager` 0.1초 주기 / Tick 비활성
- **추가 축** — Tick Group을 `TG_PrePhysics`, `TG_DuringPhysics`, `TG_PostPhysics`로 바꿔가며 총비용이 변하지 않는다는 것을 보인다
- **성공 기준** — 액터 수에 따른 게임 스레드 시간 곡선 세 개, Tick Group별 총비용이 통계적으로 구분되지 않음을 확인

### M2. Lyra의 CMC · PlayerController Tick

- **통설** — Blueprint Event Tick이 비싸다
- **가설** — Tick 하나가 끌고 들어가는 시스템의 크기가 비용을 결정한다. `UCharacterMovementComponent::TickComponent`는 함수 하나가 아니라 이동 시스템 전체의 진입점이다
- **방법** — Lyra 기본 맵에서 Insights CPU 채널을 켜고 CMC, PlayerController, BP Event Tick 스코프의 프레임당 시간을 비교
- **주의** — 이 항목만 합성 층이 아니라 기준점 층이다. 절차 문서화가 산출물이다

### M3. Blueprint vs C++

- **통설** — Blueprint는 VM에서 도니까 C++보다 느리다
- **가설** — 격차는 작업 크기가 아니라 **VM을 몇 번 경유하는가**에 비례한다. 네이티브 함수 하나를 부르는 노드 한 개는 차이가 거의 없고, 루프와 산술을 BP 노드로 돌리면 벌어진다
- **방법** — 같은 알고리즘을 세 가지로 구현한다. 순수 C++ / 전부 BP 노드 / BP에서 C++ 함수를 한 번만 호출
- **추가 축** — 반복 횟수 `1 / 10 / 100 / 1,000 / 10,000`, 빌드 구성 Development와 Shipping 양쪽
- **주의** — 빌드 구성에 따라 결과가 크게 달라지는 항목이다. 한쪽만 재고 일반화하면 안 된다

### M4. Cast의 하드 레퍼런스

- **통설** — Cast를 쓰면 레퍼런스가 생겨서 게임플레이 전에 전부 로드된다
- **가설** — `Cast To` 노드의 런타임 비용은 작다. 실제 비용은 Blueprint 에셋 사이에 생기는 로드 의존성에서 나온다. 두 가지를 분리해서 재야 한다
- **방법** — 런타임 비용은 마이크로벤치로. 로드 의존성은 Reference Viewer와 Size Map으로 참조 그래프를 뜨고, Insights `loadtime` 채널로 초기 로드 시간과 로드된 패키지 수를 잰다
- **추가** — 같은 기능을 인터페이스와 소프트 레퍼런스로 바꿨을 때 그래프가 얼마나 줄어드는지
- **프로덕션 연계** — 실제 프로젝트의 참조 그래프 크기는 여기서만 의미가 있다. 30-production.md로 뺀다

### M5. Cast vs Implements

- **통설** — 둘은 성능이 같으니 의미로 나눠 쓴다
- **가설** — 애초에 같은 질문을 하는 API가 아니다. 하나는 구체 타입을, 하나는 인터페이스 구현 여부를 묻는다. 런타임 비용 차이는 대부분의 게임 코드에서 무시할 수준이고, 실제로 갈리는 건 참조 그래프다
- **방법** — `Cast<T>`, `ImplementsInterface`, `Execute_` 경로를 각각 10^6회 호출. 성공/실패 케이스를 나눠서
- **성공 기준** — 호출당 나노초 단위 수치와, M4에서 뜬 참조 그래프 비교를 같은 문서에 나란히 둔다

### M6. ChildActorComponent

- **통설** — 쓰면 안 된다
- **가설** — 이름은 Component지만 Register 시점에 실제 Actor를 spawn하고 Unregister에서 destroy한다. 정적 배치 소수는 문제가 아니고 런타임 반복 생성·파괴가 문제다
- **방법** — N개 배치 시 레벨 로드 시간, 스폰 시간, 메모리를 잰다. 비교군은 `USceneComponent` 단독, 별도 Actor를 스폰해 Attach
- **추가 축** — 런타임 생성·파괴 빈도

### M7. GetAllActorsOfClass

- **통설** — 매우 느리다
- **가설** — `TActorIterator`가 클래스 해시 버킷을 타므로 월드의 모든 Actor를 하나씩 검사하지 않는다. 진짜 문제는 함수 자체가 아니라 매 Tick 호출이다
- **방법** — 두 축으로 스윕한다. 월드 액터 수 × 호출 빈도(1회 / 매 Tick)
- **비교군** — `ForEachObjectOfClass`, 미리 캐시한 배열, GameState 등록 방식
- **성공 기준** — 액터 수 축과 호출 빈도 축 중 어느 쪽 기울기가 가파른지 그림으로 보이기

### M8. 실시간 주기 작업과 deadline

- **통설** — 정확한 주기가 필요하면 TimerManager를 쓴다
- **가설** — Tick도 Timer도 프레임에 묶여 돌기 때문에 jitter는 남는다. 중요한 건 주기가 아니라 **deadline 초과율**이다
- **방법** — 20Hz와 30Hz 작업을 Tick과 Timer로 각각 돌리고 실제 실행 간격의 분포와 deadline miss 비율을 기록한다
- **추가 축** — 프레임 부하를 인위적으로 올려가며(더미 작업 삽입) miss 비율이 어떻게 무너지는지
- **메모** — 이 항목은 게임보다 센서 시뮬레이션 쪽 결이다. 그쪽으로 확장할 생각이 없다면 축을 줄여도 된다

### M9. Paper2D

- **성격** — 벤치보다 조사에 가깝다. 스프라이트 N개 렌더 시 드로우콜과 배칭 정도만 재고 나머지는 문서로 정리한다
- **정리할 것** — 5.8 기준으로 Sprite·Flipbook은 정식, TileMap은 Experimental, 별도 2D Physics 경로는 사실상 deprecated. Unity 2D 패키지군과의 범위 차이
- **우선순위 최하** — 시간이 없으면 문서만 남기고 측정은 생략한다

---

## 4. 리포지토리 구조

```
unreal-myth-bench/
├─ README.md                        결과 요약 · 재현 명령어 · 항목 표
├─ .gitignore                       UE 표준
├─ docs/
│  ├─ 00-plan.md                    이 문서
│  ├─ 01-protocol.md                측정 프로토콜 (첫 측정 전 확정)
│  ├─ 10-synthetic.md               M1·M3·M5·M6·M7·M8 결과
│  ├─ 20-lyra.md                    M2 재현 절차와 숫자
│  └─ 30-production.md              실제 프로젝트 사례 (수치만)
├─ MythBench/                       UE 5.8 프로젝트
│  ├─ MythBench.uproject
│  ├─ Config/
│  ├─ Content/Maps/BenchMap.umap    빈 레벨 하나
│  └─ Source/MythBench/
│     ├─ Bench/                     러너 · 환경 수집 · 결과 기록
│     └─ Scenarios/                 항목별 시나리오
├─ tools/
│  ├─ run_bench.py                  헤드리스 실행 래퍼
│  ├─ collect_env.py                머신 프로파일 수집 보조
│  ├─ parse_results.py              CSV·trace → 정규화 결과
│  └─ make_report.py                곡선 그래프 + 마크다운 생성
└─ results/
   └─ <machine-id>/<YYYY-MM-DD>/    원시 CSV · trace · env.json
```

`results/`를 머신별로 나누는 것이 중요하다. 곡선 하나에 서로 다른 머신의 데이터가 섞이면
그 그래프는 아무것도 말해주지 않는다. `make_report.py`는 섞인 입력을 받으면 실패해야 한다.

---

## 5. 환경 고정

다른 컴퓨터에서 그대로 재현할 문서이므로 버전을 못 박는다.

| 항목 | 값 | 비고 |
|---|---|---|
| 엔진 | Unreal Engine 5.8.x | 빌드 번호까지 README에 기록 |
| 소스 빌드 여부 | 런처 바이너리 | 소스 빌드로 바꾸면 결과가 달라지므로 고정 |
| IDE | Visual Studio 2022 | 툴체인 버전도 기록 |
| Python | 3.11+ | tools/ 실행용 |
| 플러그인 | 기본값 유지 | Trace는 엔진 내장. 추가 플러그인 없음 |

엔진 버전이 바뀌면 이전 결과와 같은 표에 올리지 않는다. 버전은 머신과 동급의 조건이다.

---

## 6. 프로젝트를 만든 다음에 할 일

순서대로 따라가면 된다. 각 단계 끝에 확인할 것을 적어뒀다.

### 6.1 프로젝트 생성

생성 다이얼로그에서 다음대로 고른다.

| 항목 | 값 |
|---|---|
| 카테고리 · 템플릿 | Games → Blank |
| 구현 | C++ |
| Target Platform | Desktop |
| Quality Preset | Maximum |
| Starter Content | 끄기 |
| Raytracing | 끄기 |
| 이름 · 위치 | `MythBench` · 클론한 레포 루트 |

Third Person 같은 예제 템플릿을 쓰지 않는다. 캐릭터와 CharacterMovementComponent,
애님 블루프린트, 입력 매핑이 딸려와 매 프레임 게임 스레드에서 돈다. 우리가 재려는 것이
바로 그 게임 스레드다. 에셋 수백 MB가 붙어 레포가 무거워지는 것도 문제다.

Quality Preset을 Scalable이 아니라 Maximum으로 두는 이유는 6.3에 적었다.

- 생성 후 `Content/StarterContent` 같은 게 딸려왔다면 지운다
- 경로가 `unreal-myth-bench/MythBench/MythBench.uproject`인지 확인한다
- 확인 — 에디터가 뜨고 빈 레벨이 열린다

### 6.2 리포지토리 초기화

- 루트에 UE 표준 `.gitignore`. `Binaries/`, `Intermediate/`, `Saved/`, `DerivedDataCache/` 제외
- `results/`는 커밋한다. 원시 데이터가 재현성의 근거다. 다만 trace 파일은 크므로 `*.utrace`는 제외하고 요약 CSV만 남긴다
- Git LFS는 쓰지 않는다. 에셋이 없으므로 필요 없고, 클론 문턱만 올라간다
- 확인 — `git status`가 소스와 Config, docs만 잡는다

### 6.3 측정 방해 요소 제거

`Config/DefaultEngine.ini`에 고정한다. 자세한 값은 01-protocol.md의 실행 조건 절을 따른다.

- 프레임 상한 해제, VSync 해제
- 스크린 퍼센티지 100 고정
- 자동 노출, 모션 블러 등 프레임마다 상태가 변하는 후처리 비활성
- GC 주기를 길게 잡아 측정 구간에 걸리지 않게 하고, 대신 측정 전후로 강제 GC를 한 번씩
- **스케일러빌리티 자동 감지를 끄고 값을 고정한다.** 언리얼은 첫 실행 때 하드웨어 벤치마크를
  돌려 결과를 `Saved/Config/.../GameUserSettings.ini`에 쓴다. `Saved/`는 gitignore에
  걸려 있어 머신마다 제각각 생성되므로, 같은 명령어를 돌려도 PC마다 렌더 설정이 달라진다.
  러너가 측정 시작 전에 스케일러빌리티를 코드로 강제 적용하고 그 값을 `env.json`에 남긴다
- 확인 — 빈 맵에서 `stat unit`의 프레임 시간이 흔들리지 않는다
- 확인 — 두 머신에서 같은 시나리오를 돌렸을 때 적용된 스케일러빌리티 값이 같다

### 6.4 벤치 맵

- `Content/Maps/BenchMap.umap` 하나. 빈 레벨에 PlayerStart와 고정 카메라만
- 라이트는 최소로. GPU 항목이 아닌 이상 렌더링 부하가 신호를 흐린다
- 액터를 스폰할 원점 기준만 잡아둔다
- 확인 — PIE에서 프레임 시간이 1ms 아래로 안정적으로 나온다

### 6.5 러너 골격

핵심 구조는 이렇다.

- `UBenchScenario` — `UObject` 파생 추상 클래스. `Setup(int32 N)` / `RunFrame()` / `Teardown()` / `GetName()`
- `UBenchSubsystem` — `UGameInstanceSubsystem`. 시나리오 등록, 커맨드라인 파싱, 워밍업·측정·반복 루프, 결과 기록
- `FBenchRunSpec` — 시나리오명, N, 워밍업 프레임, 측정 프레임, 반복 횟수, 출력 경로
- `FBenchEnvironment` — CPU·GPU·RAM·OS·엔진 버전·빌드 구성을 수집해 `env.json`으로 떨군다

커맨드라인 형식을 여기서 확정한다.

```
-bench=<시나리오명> -N=<정수> -warmup=<프레임> -frames=<프레임> -repeats=<횟수> -out=<경로>
```

확인 — 시나리오 없이 실행해도 `env.json`이 정상적으로 나온다

### 6.6 첫 시나리오로 파이프라인 관통

M1(Tick vs Timer) 하나만 구현해서 **끝까지** 흘려본다.
러너 → 헤드리스 실행 → CSV → 파싱 → 그래프 → 마크다운 리포트.

여기서 결과 스키마가 확정된다. 나중에 컬럼을 바꾸면 앞서 뽑은 데이터를 다 버리게 되므로
이 단계에서 충분히 고민한다.

- 확인 — 명령어 한 줄로 `results/<machine-id>/<date>/` 아래에 CSV와 그래프가 생긴다

### 6.7 나머지 항목

M3, M5, M6, M7, M8을 같은 틀에 얹는다. 여기부터는 기계적인 작업이다.
M4는 도구가 다르므로(Reference Viewer, loadtime 채널) 별도 취급한다.

### 6.8 CI

기존 Jenkins 파이프라인에 물린다.
`-nullrhi`로 CPU 항목만 돌리면 헤드리스 머신에서도 돈다.
회귀 감지가 목적이 아니라 **명령어 한 줄로 전체가 재현된다는 증거**가 목적이다.

---

## 7. 결과 스키마

CSV 한 행이 한 번의 반복이다.

```
run_id, timestamp_utc, machine_id, cpu, gpu, ram_gb, os,
engine_version, build_config, scenario, param_n, param_extra,
repeat_index, warmup_frames, measured_frames,
frame_ms_median, frame_ms_p95, frame_ms_min, frame_ms_max,
game_ms_median, draw_ms_median, gpu_ms_median,
custom_stat_name, custom_stat_median, notes
```

평균은 넣지 않는다. 프레임 시간 분포는 한쪽으로 치우쳐 있어서 평균이 실제를 왜곡한다.
중앙값과 P95를 기본으로 쓴다.

---

## 8. 마일스톤

| | 내용 | 완료 조건 |
|---|---|---|
| M0 | 프로토콜 확정 | 01-protocol.md 완성. 이후 조건 변경 금지 |
| M1 | 파이프라인 관통 | 시나리오 1개가 명령어 한 줄로 리포트까지 |
| M2 | 마이크로벤치 확장 | M3·M5·M6·M7·M8 완료 |
| M3 | 로드·의존성 | M4 완료. Reference Viewer와 loadtime 채널 |
| M4 | Lyra 기준점 | 20-lyra.md 완성. 재현 절차 포함 |
| M5 | 프로덕션 사례 | 30-production.md 완성. 수치와 그래프만 |
| M6 | 공개 정리 | README에 항목 표와 결론, 재현 명령어 |

M1까지가 실질적인 고비다. 거기를 넘으면 나머지는 같은 틀의 반복이다.

---

## 9. 포트폴리오로서의 산출물

- 항목별 "통설 / 실측 / 성립 조건" 표. 이게 README의 얼굴이 된다
- 스케일 곡선 그래프. 단일 수치보다 훨씬 강하다
- 재현 명령어. 리뷰어가 직접 돌려볼 수 있다는 게 이 프로젝트의 신뢰도 전부다
- 머신별 비교표. 하드웨어가 결과를 어디까지 바꾸는지

면접에서 꺼낼 이야기는 항목 수만큼 나온다.
"GetAllActorsOfClass가 느리다고들 하는데 재보니 액터 수보다 호출 빈도가 지배적이었다" 같은
문장을 그래프와 함께 낼 수 있으면 그것으로 충분하다.
