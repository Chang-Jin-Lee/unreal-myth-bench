// M1. "Tick을 쓰지 마라"가 어디서부터 참이 되는지 본다.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Bench/BenchScenario.h"
#include "TickVsTimerScenario.generated.h"

UENUM()
enum class EBenchDummyMode : uint8
{
	Tick,      // 빈 TickActor
	Timer,     // TimerManager 0.1초 주기
	Disabled   // 아무것도 하지 않는다. 스폰 비용만 남는 대조군
};

/** 조건에 따라 Tick 또는 Timer 로만 카운터를 올리는 최소 액터. */
UCLASS()
class MYTHBENCH_API ABenchDummyActor : public AActor
{
	GENERATED_BODY()

public:
	ABenchDummyActor();

	void Configure(EBenchDummyMode InMode, ETickingGroup InTickGroup);

	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	void OnTimer();

	EBenchDummyMode Mode = EBenchDummyMode::Disabled;
	FTimerHandle TimerHandle;

	// 컴파일러가 틱 본문을 통째로 날리지 않게 붙잡아 두는 값.
	volatile int64 Counter = 0;
};

UCLASS()
class MYTHBENCH_API UTickVsTimerScenario : public UBenchScenario
{
	GENERATED_BODY()

public:
	virtual FName GetScenarioName() const override { return FName(TEXT("TickVsTimer")); }
	virtual void Setup(UWorld* InWorld, const FBenchRunSpec& InSpec) override;
	virtual void Teardown() override;
	virtual FString GetParamExtra() const override;

private:
	EBenchDummyMode ParseMode(const FString& In) const;
	ETickingGroup ParseTickGroup(const FString& In) const;

	UPROPERTY()
	TArray<TObjectPtr<AActor>> Spawned;
};
