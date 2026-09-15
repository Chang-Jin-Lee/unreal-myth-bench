#include "Scenarios/GetAllActorsScenario.h"

#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UObjectHash.h"

ABenchSearchTargetActor::ABenchSearchTargetActor()
{
	PrimaryActorTick.bCanEverTick = false;
	PrimaryActorTick.bStartWithTickEnabled = false;
	SetActorEnableCollision(false);
	bReplicates = false;
}

EBenchSearchMode UGetAllActorsScenario::ParseMode(const FString& In) const
{
	const FString Key = In.ToLower();
	if (Key == TEXT("once"))      { return EBenchSearchMode::Once; }
	if (Key == TEXT("everytick")) { return EBenchSearchMode::EveryTick; }
	if (Key == TEXT("cached"))    { return EBenchSearchMode::Cached; }
	if (Key == TEXT("foreach"))   { return EBenchSearchMode::ForEach; }
	return EBenchSearchMode::Disabled;
}

void UGetAllActorsScenario::Setup(UWorld* InWorld, const FBenchRunSpec& InSpec)
{
	Super::Setup(InWorld, InSpec);
	if (!InWorld)
	{
		return;
	}

	Mode = ParseMode(InSpec.Mode);

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

	Spawned.Reserve(InSpec.N);
	for (int32 Index = 0; Index < InSpec.N; ++Index)
	{
		AActor* Actor = InWorld->SpawnActor<ABenchSearchTargetActor>(
			ABenchSearchTargetActor::StaticClass(), FTransform::Identity, Params);
		if (Actor)
		{
			Spawned.Add(Actor);
		}
	}

	// Once 와 Cached 는 측정 구간 밖에서 한 번만 부른다.
	// Once 가 대조군과 구분되지 않는 값이 나오는 것 자체가 이 항목 결론의 절반이다.
	// "함수가 느리다" 가 아니라 "매 프레임 부르는 것이 문제다" 라는 쪽.
	if (Mode == EBenchSearchMode::Once || Mode == EBenchSearchMode::Cached)
	{
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsOfClass(InWorld, ABenchSearchTargetActor::StaticClass(), Found);
		Sink += Found.Num();

		if (Mode == EBenchSearchMode::Cached)
		{
			CachedActors.Reserve(Found.Num());
			for (AActor* Actor : Found)
			{
				CachedActors.Add(Actor);
			}
		}
	}
}

void UGetAllActorsScenario::RunFrame(float DeltaSeconds)
{
	UWorld* CurrentWorld = World.Get();

	switch (Mode)
	{
	case EBenchSearchMode::EveryTick:
	{
		if (!CurrentWorld)
		{
			break;
		}
		// TArray 를 매번 새로 만드는 것까지가 실제 호출자가 치르는 비용이다.
		// 밖으로 빼서 재사용하면 이 항목이 재려는 것과 다른 것을 재게 된다.
		TArray<AActor*> Found;
		UGameplayStatics::GetAllActorsOfClass(CurrentWorld, ABenchSearchTargetActor::StaticClass(), Found);
		Sink += Found.Num();
		break;
	}
	case EBenchSearchMode::Cached:
	{
		// 캐시한 배열이 대안으로서 얼마나 싼지 보는 비교군. 유효성 검사까지 포함해야
		// 실제로 캐시를 쓰는 코드와 같은 일을 한 것이 된다.
		int64 Live = 0;
		for (const TObjectPtr<AActor>& Actor : CachedActors)
		{
			Live += IsValid(Actor) ? 1 : 0;
		}
		Sink += Live;
		break;
	}
	case EBenchSearchMode::ForEach:
	{
		// GetAllActorsOfClass 와 의미가 완전히 같지는 않다. 이쪽은 월드와 무관하게
		// 해당 클래스의 모든 UObject 를 훑는다. 월드가 하나뿐인 이 벤치에서는
		// 비교 가능하지만, 결과를 옮겨 적을 때 이 차이를 빼놓으면 안 된다.
		int64 Count = 0;
		ForEachObjectOfClass(ABenchSearchTargetActor::StaticClass(),
			[&Count](UObject*) { ++Count; });
		Sink += Count;
		break;
	}
	default:
		// Disabled 와 Once 는 측정 구간에서 아무것도 하지 않는다.
		break;
	}
}

void UGetAllActorsScenario::Teardown()
{
	CachedActors.Reset();

	for (TObjectPtr<AActor>& Actor : Spawned)
	{
		if (IsValid(Actor))
		{
			Actor->Destroy();
		}
	}
	Spawned.Reset();
}

FString UGetAllActorsScenario::GetParamExtra() const
{
	// M1 과 달리 tickgroup 축이 없다. 이 항목에서 틱 그룹은 의미가 없으므로 넣지 않는다.
	return FString::Printf(TEXT("mode=%s"),
		Spec.Mode.IsEmpty() ? TEXT("disabled") : *Spec.Mode);
}
