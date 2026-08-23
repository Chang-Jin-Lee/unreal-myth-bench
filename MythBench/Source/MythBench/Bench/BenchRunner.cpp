#include "Bench/BenchRunner.h"

#include "Bench/BenchScenario.h"
#include "Scenarios/TickVsTimerScenario.h"

#include "Engine/World.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ProfilingDebugging/CsvProfiler.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "ProfilingDebugging/MiscTrace.h"
#include "RenderCore.h"
#include "Scalability.h"

DEFINE_LOG_CATEGORY_STATIC(LogBench, Log, All);

CSV_DEFINE_CATEGORY(Bench, true);

namespace
{
	/** -bench= 이름을 클래스로 옮긴다. 항목이 늘면 여기에 한 줄 추가한다. */
	UBenchScenario* CreateScenario(const FString& Name, UObject* Outer)
	{
		const FString Key = Name.ToLower();
		if (Key == TEXT("tickvstimer"))
		{
			return NewObject<UTickVsTimerScenario>(Outer);
		}
		return nullptr;
	}

	/** ini 가 무시되는 경로가 있어 코드에서 한 번 더 박는다. */
	void ForceMeasurementCVars()
	{
		static const TCHAR* Commands[] = {
			TEXT("t.MaxFPS 0"),
			TEXT("r.VSync 0"),
			TEXT("r.ScreenPercentage 100"),
			TEXT("r.DynamicRes.OperationMode 0"),
			TEXT("gc.CollectGarbageEveryFrame 0"),
		};

		for (const TCHAR* Command : Commands)
		{
			GEngine->Exec(nullptr, Command);
		}

		Scalability::FQualityLevels Levels;
		Levels.SetFromSingleQualityLevel(3);
		Scalability::SetQualityLevels(Levels);
	}
}

ABenchRunner::ABenchRunner()
{
	PrimaryActorTick.bCanEverTick = true;
	// 시나리오 액터보다 먼저 돌아야 프레임 경계를 잡을 수 있다.
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	bReplicates = false;
}

void ABenchRunner::BeginPlay()
{
	Super::BeginPlay();

	Spec = FBenchRunSpec::FromCommandLine();
	if (!Spec.IsValid())
	{
		UE_LOG(LogBench, Error, TEXT("bench= 와 out= 이 모두 필요하다. 종료한다."));
		FPlatformMisc::RequestExit(false);
		return;
	}

	ForceMeasurementCVars();
	Environment = FBenchEnvironment::Collect(Spec.MachineId);

	Scenario = CreateScenario(Spec.Scenario, this);
	if (!Scenario)
	{
		UE_LOG(LogBench, Error, TEXT("모르는 시나리오다: %s"), *Spec.Scenario);
		FPlatformMisc::RequestExit(false);
		return;
	}

	UE_LOG(LogBench, Display, TEXT("%s"), *Spec.Describe());
	Scenario->Setup(GetWorld(), Spec);

	TRACE_BOOKMARK(TEXT("BenchWarmupStart"));
	LastFrameStartSeconds = FPlatformTime::Seconds();
}

void ABenchRunner::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bFinished || !Scenario)
	{
		return;
	}

	const double Now = FPlatformTime::Seconds();
	const double FrameMs = (Now - LastFrameStartSeconds) * 1000.0;
	LastFrameStartSeconds = Now;

	if (!bMeasuring && FrameIndex >= Spec.WarmupFrames)
	{
		BeginMeasuring();
	}

	double ScenarioMs = 0.0;
	{
		const double ScenarioStart = FPlatformTime::Seconds();
		{
			TRACE_CPUPROFILER_EVENT_SCOPE(MythBench_ScenarioFrame);
			CSV_SCOPED_TIMING_STAT(Bench, ScenarioFrame);
			Scenario->RunFrame(DeltaSeconds);
		}
		ScenarioMs = (FPlatformTime::Seconds() - ScenarioStart) * 1000.0;
	}

	if (bMeasuring)
	{
		CSV_CUSTOM_STAT(Bench, ParamN, Spec.N, ECsvCustomStatOp::Set);

		FrameSamplesMs.Add(FrameMs);
		ScenarioSamplesMs.Add(ScenarioMs);
		GameThreadSamplesMs.Add(FPlatformTime::ToMilliseconds(GGameThreadTime));
		RenderThreadSamplesMs.Add(FPlatformTime::ToMilliseconds(GRenderThreadTime));
		GpuSamplesMs.Add(FPlatformTime::ToMilliseconds(GGPUFrameTime));

		if (FrameSamplesMs.Num() >= Spec.MeasureFrames)
		{
			FinishAndExit();
			return;
		}
	}

	++FrameIndex;
}

void ABenchRunner::BeginMeasuring()
{
	// 측정 구간에 GC가 걸리면 그 프레임만 튄다. 들어가기 직전에 한 번 비운다.
	GEngine->ForceGarbageCollection(true);

	bMeasuring = true;
	TRACE_BOOKMARK(TEXT("BenchMeasureStart"));
	FCsvProfiler::Get()->BeginCapture();
	UE_LOG(LogBench, Display, TEXT("측정 시작. 워밍업 %d 프레임 끝."), Spec.WarmupFrames);
}

void ABenchRunner::FinishAndExit()
{
	bFinished = true;
	FCsvProfiler::Get()->EndCapture();
	TRACE_BOOKMARK(TEXT("BenchMeasureEnd"));

	Scenario->Teardown();
	WriteResults();

	UE_LOG(LogBench, Display, TEXT("측정 끝. 결과: %s"), *Spec.OutDir);
	FPlatformMisc::RequestExit(false);
}

void ABenchRunner::WriteResults()
{
	const FString OutDir = FPaths::ConvertRelativePathToFull(Spec.OutDir);

	// 통계는 배열을 정렬하므로 원본 CSV를 먼저 쓴다. 프레임 순서가 남아야 히치가 보인다.
	FString Raw = TEXT("frame_ms,scenario_ms,game_ms,render_ms,gpu_ms\n");
	for (int32 Index = 0; Index < FrameSamplesMs.Num(); ++Index)
	{
		Raw += FString::Printf(TEXT("%.4f,%.4f,%.4f,%.4f,%.4f\n"),
			FrameSamplesMs[Index], ScenarioSamplesMs[Index], GameThreadSamplesMs[Index],
			RenderThreadSamplesMs[Index], GpuSamplesMs[Index]);
	}
	FFileHelper::SaveStringToFile(Raw, *FPaths::Combine(OutDir, TEXT("frames.csv")));

	const FBenchStats Frame    = FBenchStats::FromSamples(FrameSamplesMs);
	const FBenchStats ScenarioS= FBenchStats::FromSamples(ScenarioSamplesMs);
	const FBenchStats GameT    = FBenchStats::FromSamples(GameThreadSamplesMs);
	const FBenchStats RenderT  = FBenchStats::FromSamples(RenderThreadSamplesMs);
	const FBenchStats Gpu      = FBenchStats::FromSamples(GpuSamplesMs);

	const FString Summary = FString::Printf(
		TEXT("{\n")
		TEXT("  \"scenario\": \"%s\",\n")
		TEXT("  \"param_n\": %d,\n")
		TEXT("  \"param_extra\": \"%s\",\n")
		TEXT("  \"repeat_index\": %d,\n")
		TEXT("  \"warmup_frames\": %d,\n")
		TEXT("  \"measured_frames\": %d,\n")
		TEXT("  \"frame_ms\":       { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"scenario_ms\":    { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"game_ms\":        { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"render_ms\":      { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"gpu_ms\":         { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"environment\": %s")
		TEXT("}\n"),
		*BenchJson::Escape(Spec.Scenario), Spec.N,
		*BenchJson::Escape(Scenario->GetParamExtra()), Spec.RepeatIndex,
		Spec.WarmupFrames, Frame.Count,
		Frame.Median, Frame.P95, Frame.Min, Frame.Max,
		ScenarioS.Median, ScenarioS.P95, ScenarioS.Min, ScenarioS.Max,
		GameT.Median, GameT.P95, GameT.Min, GameT.Max,
		RenderT.Median, RenderT.P95, RenderT.Min, RenderT.Max,
		Gpu.Median, Gpu.P95, Gpu.Min, Gpu.Max,
		*Environment.ToJson());

	FFileHelper::SaveStringToFile(Summary, *FPaths::Combine(OutDir, TEXT("summary.json")));
	FFileHelper::SaveStringToFile(Environment.ToJson(), *FPaths::Combine(OutDir, TEXT("env.json")));

}
