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
	int32   WarmupFrames  = 120;
	int32   MeasureFrames = 600;
	int32   RepeatIndex   = 0;
	FString MachineId;
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
	FString Cpu;
	FString Gpu;
	FString Os;
	FString EngineVersion;
	FString BuildConfig;
	FString Rhi;
	int32   RamGb = 0;
	bool    bSubstrate = false;
	TMap<FString, int32> Scalability;

	static FBenchEnvironment Collect(const FString& InMachineId);
	FString ToJson() const;
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

namespace BenchJson
{
	/** 따옴표와 역슬래시만 막는다. 우리가 쓰는 값에 제어문자는 들어오지 않는다. */
	MYTHBENCH_API FString Escape(const FString& In);
}
