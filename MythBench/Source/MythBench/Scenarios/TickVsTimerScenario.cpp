#include "Scenarios/TickVsTimerScenario.h"

#include "Engine/World.h"
#include "TimerManager.h"

ABenchDummyActor::ABenchDummyActor()
{
	PrimaryActorTick.bCanEverTick = false;
	PrimaryActorTick.bStartWithTickEnabled = false;
	SetActorEnableCollision(false);
	bReplicates = false;
}

void ABenchDummyActor::Configure(EBenchDummyMode InMode, ETickingGroup InTickGroup)
{
	Mode = InMode;
	const bool bWantsTick = (Mode == EBenchDummyMode::Tick);

	PrimaryActorTick.bCanEverTick = bWantsTick;
	PrimaryActorTick.bStartWithTickEnabled = bWantsTick;
	PrimaryActorTick.TickGroup = InTickGroup;
}

void ABenchDummyActor::BeginPlay()
{
	Super::BeginPlay();

	if (Mode == EBenchDummyMode::Timer)
	{
		GetWorldTimerManager().SetTimer(
			TimerHandle, this, &ABenchDummyActor::OnTimer, 0.1f, /*bLoop=*/true);
	}
}

void ABenchDummyActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	Counter = Counter + 1;
}

void ABenchDummyActor::OnTimer()
{
	Counter = Counter + 1;
}

EBenchDummyMode UTickVsTimerScenario::ParseMode(const FString& In) const
{
	const FString Key = In.ToLower();
	if (Key == TEXT("tick"))  { return EBenchDummyMode::Tick; }
	if (Key == TEXT("timer")) { return EBenchDummyMode::Timer; }
	return EBenchDummyMode::Disabled;
}

ETickingGroup UTickVsTimerScenario::ParseTickGroup(const FString& In) const
{
	if (In == TEXT("duringphysics")) { return TG_DuringPhysics; }
	if (In == TEXT("postphysics"))   { return TG_PostPhysics; }
	return TG_PrePhysics;
}

void UTickVsTimerScenario::Setup(UWorld* InWorld, const FBenchRunSpec& InSpec)
{
	Super::Setup(InWorld, InSpec);
	if (!InWorld)
	{
		return;
	}

	const EBenchDummyMode DummyMode = ParseMode(InSpec.Mode);
	const ETickingGroup Group = ParseTickGroup(InSpec.TickGroup);

	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.bDeferConstruction = true;

	Spawned.Reserve(InSpec.N);
	for (int32 Index = 0; Index < InSpec.N; ++Index)
	{
		ABenchDummyActor* Actor = InWorld->SpawnActor<ABenchDummyActor>(
			ABenchDummyActor::StaticClass(), FTransform::Identity, Params);
		if (!Actor)
		{
			continue;
		}

		// 스폰을 미뤄 두고 틱 설정을 끝낸 뒤 마무리해야 BeginPlay 전에 반영된다.
		Actor->Configure(DummyMode, Group);
		Actor->FinishSpawning(FTransform::Identity);
		Spawned.Add(Actor);
	}
}

void UTickVsTimerScenario::Teardown()
{
	for (TObjectPtr<AActor>& Actor : Spawned)
	{
		if (IsValid(Actor))
		{
			Actor->Destroy();
		}
	}
	Spawned.Reset();
}

FString UTickVsTimerScenario::GetParamExtra() const
{
	return FString::Printf(TEXT("mode=%s;tickgroup=%s"),
		Spec.Mode.IsEmpty() ? TEXT("disabled") : *Spec.Mode, *Spec.TickGroup);
}
