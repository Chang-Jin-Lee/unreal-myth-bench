// M7. "GetAllActorsOfClass 는 매우 느리다" 가 어느 축에서 참이 되는지 본다.
//
// 두 축을 따로 움직인다. 월드 액터 수는 -N 으로, 호출 빈도와 비교군은 -mode 로.
// 통설이 지목하는 것은 함수 자체지만, 가설은 액터 수 축보다 호출 빈도 축이
// 지배적이라는 것이다. 둘을 한 번에 움직이면 어느 쪽 기울기가 가파른지 알 수 없다.
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Bench/BenchScenario.h"
#include "GetAllActorsScenario.generated.h"

UENUM()
enum class EBenchSearchMode : uint8
{
	Disabled,   // 호출하지 않는다. 스폰 비용만 남는 대조군
	Once,       // Setup 에서 1회. 측정 구간에서는 0회다
	EveryTick,  // 매 프레임 GetAllActorsOfClass
	Cached,     // Setup 에서 채운 배열을 매 프레임 순회
	ForEach,    // 매 프레임 ForEachObjectOfClass
};

/**
 * 검색 대상. 찾히는 것 말고는 아무것도 하지 않는다.
 *
 * M1 의 ABenchDummyActor 를 재사용하지 않는 이유는 그쪽이 Tick 과 Timer 를 켜고 끄는
 * 액터라서다. 검색 비용을 재는 항목의 대상이 틱 설정에 따라 성격이 바뀌면 두 항목이
 * 서로를 오염시킨다.
 */
UCLASS()
class MYTHBENCH_API ABenchSearchTargetActor : public AActor
{
	GENERATED_BODY()

public:
	ABenchSearchTargetActor();
};

UCLASS()
class MYTHBENCH_API UGetAllActorsScenario : public UBenchScenario
{
	GENERATED_BODY()

public:
	virtual FName GetScenarioName() const override { return FName(TEXT("GetAllActors")); }
	virtual void Setup(UWorld* InWorld, const FBenchRunSpec& InSpec) override;
	virtual void RunFrame(float DeltaSeconds) override;
	virtual void Teardown() override;
	virtual FString GetParamExtra() const override;

private:
	EBenchSearchMode ParseMode(const FString& In) const;

	EBenchSearchMode Mode = EBenchSearchMode::Disabled;

	UPROPERTY()
	TArray<TObjectPtr<AActor>> Spawned;

	/** Cached 모드가 매 프레임 순회할 배열. Setup 에서 한 번 채운다. */
	UPROPERTY()
	TArray<TObjectPtr<AActor>> CachedActors;

	// 컴파일러가 "검색 결과를 아무도 안 쓴다" 고 보고 호출을 통째로 날리지 않게 붙잡는다.
	// M1 의 ABenchDummyActor::Counter 와 같은 이유다.
	volatile int64 Sink = 0;
};
