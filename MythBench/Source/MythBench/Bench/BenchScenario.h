// 시나리오 인터페이스. 항목 하나가 클래스 하나다.
#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "Bench/BenchCommon.h"
#include "BenchScenario.generated.h"

UCLASS(Abstract)
class MYTHBENCH_API UBenchScenario : public UObject
{
	GENERATED_BODY()

public:
	/** -bench= 로 넘어오는 이름. 소문자로 비교한다. */
	virtual FName GetScenarioName() const { return NAME_None; }

	/** 워밍업 전에 한 번. 여기서 액터를 스폰한다. */
	virtual void Setup(UWorld* InWorld, const FBenchRunSpec& InSpec) { World = InWorld; Spec = InSpec; }

	/** 매 프레임. 측정 구간에서는 이 호출이 CSV 스코프에 감긴다. */
	virtual void RunFrame(float DeltaSeconds) {}

	/** 측정이 끝난 뒤 정리. */
	virtual void Teardown() {}

	/** 리포트에 남길 추가 축. 없으면 빈 문자열. */
	virtual FString GetParamExtra() const { return FString(); }

protected:
	TWeakObjectPtr<UWorld> World;
	FBenchRunSpec Spec;
};
