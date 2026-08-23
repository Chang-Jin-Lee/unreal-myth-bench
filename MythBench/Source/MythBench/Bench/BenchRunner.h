// 워밍업과 측정 구간을 관리하고 결과를 파일로 남기는 액터.
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
	void WriteResults();

	UPROPERTY()
	TObjectPtr<UBenchScenario> Scenario = nullptr;

	FBenchRunSpec Spec;
	FBenchEnvironment Environment;

	int32 FrameIndex = 0;
	bool  bMeasuring = false;
	bool  bFinished  = false;

	double LastFrameStartSeconds = 0.0;

	TArray<double> FrameSamplesMs;
	TArray<double> ScenarioSamplesMs;
	TArray<double> GameThreadSamplesMs;
	TArray<double> RenderThreadSamplesMs;
	TArray<double> GpuSamplesMs;
};
