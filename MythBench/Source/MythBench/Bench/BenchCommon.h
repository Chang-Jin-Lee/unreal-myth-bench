// 벤치 실행 스펙, 환경 정보, 통계. 엔진 타입 의존을 최소로 유지한다.
#pragma once

#include "CoreMinimal.h"

/**
 * 한 번의 프로세스 실행이 무엇을 재는지 기술한다.
 * 반복은 프로세스 재시작 단위이므로 RepeatIndex 도 여기에 들어온다.
 */
struct MYTHBENCH_API FBenchRunSpec
{
	FString Scenario;
	int32   N             = 0;
	FString Mode;                 // 시나리오별 추가 축
	FString TickGroup     = TEXT("prephysics");

	// 프레임 수가 아니라 시간으로 자른다. 프레임 시간 자체가 측정 대상이라
	// 프레임 수로 자르면 조건마다 측정 창 길이가 달라진다.
	double  WarmupSeconds  = 3.0;
	double  MeasureSeconds = 10.0;
	int32   MaxFrames      = 200000;   // 메모리 상한. 정상 실행에서는 걸리지 않는다

	int32   RepeatIndex   = 0;
	FString MachineId;
	FString AffinityNote;         // 런처가 적용한 코어 고정. 기록용
	FString OutDir;

	static FBenchRunSpec FromCommandLine();

	bool IsValid() const { return !Scenario.IsEmpty() && !OutDir.IsEmpty(); }
	FString Describe() const;
};

/**
 * 측정 머신과 빌드 정보. 숫자보다 이게 먼저다.
 * 여기 값이 다르면 두 결과는 같은 그래프에 올릴 수 없다.
 */
struct MYTHBENCH_API FBenchEnvironment
{
	FString MachineId;
	/**
	 * 실제로 이 측정을 찍은 머신의 호스트명. MachineId 는 사람이 붙이는
	 * 이름이고 -machineid 로 넘어오는 평범한 인자이므로, 다른 머신에서
	 * 남의 이름으로 돌려도 결과 파일만 봐서는 알 수 없다. Hostname 은
	 * 그 불일치를 사후에 잡을 수 있게 하는 유일한 장치다.
	 */
	FString Hostname;
	FString Cpu;
	FString Gpu;
	FString Os;
	FString EngineVersion;
	FString BuildConfig;
	FString Rhi;
	FString Affinity;
	int32   RamGb = 0;
	int32   CoreCount = 0;
	bool    bSubstrate = false;
	TMap<FString, int32> Scalability;

	static FBenchEnvironment Collect(const FBenchRunSpec& Spec);
	FString ToJson() const;
	/** run.log 첫머리에 한 줄로 남긴다. 로그만 봐도 어디서 잰 건지 알 수 있게. */
	FString OneLine() const;
};

/**
 * 프레임 샘플 통계. 평균은 의도적으로 빠져 있다.
 * 프레임 시간 분포는 오른쪽 꼬리가 길어서 평균이 체감과 어긋난다.
 */
struct MYTHBENCH_API FBenchStats
{
	double Median = 0.0;
	double P95    = 0.0;
	double Min    = 0.0;
	double Max    = 0.0;
	int32  Count  = 0;

	/** Samples 를 정렬하므로 참조로 받는다. */
	static FBenchStats FromSamples(TArray<double>& Samples);
};

/** 측정 품질. 러너가 스스로 판정해 로그와 summary 에 남긴다. */
struct MYTHBENCH_API FBenchQuality
{
	int32  HitchCount = 0;       // 중앙값 1.5배 초과 프레임
	double HitchRatio = 0.0;
	double MeasuredSeconds = 0.0;
	double AverageFps = 0.0;
	bool   bRenderBound = false; // render_ms 중앙값이 game_ms 중앙값보다 크다

	TArray<FString> Warnings;    // 사람이 읽을 경고. 비어 있으면 깨끗한 실행이다
};

namespace BenchJson
{
	/** 따옴표와 역슬래시만 막는다. 우리가 쓰는 값에 제어문자는 들어오지 않는다. */
	MYTHBENCH_API FString Escape(const FString& In);
}
