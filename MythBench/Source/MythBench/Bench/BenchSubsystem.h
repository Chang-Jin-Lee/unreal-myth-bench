// -bench= 가 있으면 러너를 월드에 띄운다. 없으면 아무 일도 하지 않는다.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "BenchSubsystem.generated.h"

UCLASS()
class MYTHBENCH_API UBenchSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
