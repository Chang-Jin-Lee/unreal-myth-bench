// 워밍업과 측정 구간을 시간으로 자르고, 품질을 스스로 판정해 기록하는 액터.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Bench/BenchCommon.h"
#include "BenchRunner.generated.h"

class UBenchScenario;

UCLASS()
class MYTHBENCH_API ABenchRunner : public AActor
{
	GENERATED_BODY()

public:
	ABenchRunner();

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	void BeginMeasuring();
	void FinishAndExit();
	FBenchQuality Judge() const;
	void LogSummary(const FBenchQuality& Quality) const;
	void WriteResults(const FBenchQuality& Quality);

	UPROPERTY()
	TObjectPtr<UBenchScenario> Scenario = nullptr;

	FBenchRunSpec Spec;
	FBenchEnvironment Environment;

	bool bMeasuring = false;
	bool bFinished  = false;

	double StartSeconds        = 0.0;
	double MeasureStartSeconds = 0.0;
	double MeasureEndSeconds   = 0.0;
	double LastFrameStartSeconds = 0.0;

	TArray<double> FrameSamplesMs;
	TArray<double> ScenarioSamplesMs;
	TArray<double> GameThreadSamplesMs;
	TArray<double> RenderThreadSamplesMs;
	TArray<double> GpuSamplesMs;
};
