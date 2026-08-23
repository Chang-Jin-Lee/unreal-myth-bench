#include "Bench/BenchSubsystem.h"

#include "Bench/BenchCommon.h"
#include "Bench/BenchRunner.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

bool UBenchSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// 벤치 인자가 없으면 에디터를 평범하게 쓰는 상황이다. 끼어들지 않는다.
	FString Unused;
	return FParse::Value(FCommandLine::Get(), TEXT("bench="), Unused);
}

void UBenchSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);

	if (InWorld.WorldType != EWorldType::Game && InWorld.WorldType != EWorldType::PIE)
	{
		return;
	}

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	InWorld.SpawnActor<ABenchRunner>(ABenchRunner::StaticClass(), FTransform::Identity, Params);
}
