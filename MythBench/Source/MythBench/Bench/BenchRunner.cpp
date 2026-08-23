#include "Bench/BenchRunner.h"

#include "Bench/BenchScenario.h"
#include "Scenarios/TickVsTimerScenario.h"

#include "DynamicRHI.h"
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
	Environment = FBenchEnvironment::Collect(Spec);

	// run.log 만 봐도 어디서 무엇을 쟀는지 알 수 있어야 한다.
	UE_LOG(LogBench, Display, TEXT("=== MythBench 시작 ==="));
	UE_LOG(LogBench, Display, TEXT("[env] %s"), *Environment.OneLine());
	UE_LOG(LogBench, Display, TEXT("[out] %s"), *Spec.OutDir);

	Scenario = CreateScenario(Spec.Scenario, this);
	if (!Scenario)
	{
		UE_LOG(LogBench, Error, TEXT("모르는 시나리오다: %s"), *Spec.Scenario);
		FPlatformMisc::RequestExit(false);
		return;
	}

	UE_LOG(LogBench, Display, TEXT("[spec] %s"), *Spec.Describe());
	Scenario->Setup(GetWorld(), Spec);

	TRACE_BOOKMARK(TEXT("BenchWarmupStart"));
	StartSeconds = LastFrameStartSeconds = FPlatformTime::Seconds();
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

	if (!bMeasuring && (Now - StartSeconds) >= Spec.WarmupSeconds)
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
		GpuSamplesMs.Add(FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()));

		const bool bTimeUp  = (Now - MeasureStartSeconds) >= Spec.MeasureSeconds;
		const bool bCapHit  = FrameSamplesMs.Num() >= Spec.MaxFrames;
		if (bTimeUp || bCapHit)
		{
			MeasureEndSeconds = Now;
			if (bCapHit && !bTimeUp)
			{
				UE_LOG(LogBench, Warning,
					TEXT("[quality] maxframes(%d) 에 먼저 걸렸다. 측정 창이 의도보다 짧다."),
					Spec.MaxFrames);
			}
			FinishAndExit();
			return;
		}
	}
}

void ABenchRunner::BeginMeasuring()
{
	// 측정 구간에 GC가 걸리면 그 프레임만 튄다. 들어가기 직전에 한 번 비운다.
	GEngine->ForceGarbageCollection(true);

	bMeasuring = true;
	MeasureStartSeconds = FPlatformTime::Seconds();
	TRACE_BOOKMARK(TEXT("BenchMeasureStart"));
	FCsvProfiler::Get()->BeginCapture();
	UE_LOG(LogBench, Display, TEXT("[phase] 워밍업 %.2f초 종료. 측정 %.1f초 시작."),
		MeasureStartSeconds - StartSeconds, Spec.MeasureSeconds);
}

void ABenchRunner::FinishAndExit()
{
	bFinished = true;
	FCsvProfiler::Get()->EndCapture();
	TRACE_BOOKMARK(TEXT("BenchMeasureEnd"));

	Scenario->Teardown();

	const FBenchQuality Quality = Judge();
	LogSummary(Quality);
	WriteResults(Quality);

	FPlatformMisc::RequestExit(false);
}

FBenchQuality ABenchRunner::Judge() const
{
	FBenchQuality Q;
	if (FrameSamplesMs.Num() == 0)
	{
		Q.Warnings.Add(TEXT("측정 샘플이 없다"));
		return Q;
	}

	TArray<double> Sorted = FrameSamplesMs;
	Sorted.Sort();
	const double FrameMedian = Sorted[Sorted.Num() / 2];

	for (double Sample : FrameSamplesMs)
	{
		if (Sample > FrameMedian * 1.5)
		{
			++Q.HitchCount;
		}
	}
	Q.HitchRatio      = static_cast<double>(Q.HitchCount) / FrameSamplesMs.Num();
	Q.MeasuredSeconds = MeasureEndSeconds - MeasureStartSeconds;
	Q.AverageFps      = Q.MeasuredSeconds > 0.0 ? FrameSamplesMs.Num() / Q.MeasuredSeconds : 0.0;

	TArray<double> Game = GameThreadSamplesMs;
	TArray<double> Render = RenderThreadSamplesMs;
	Game.Sort();
	Render.Sort();
	const double GameMedian   = Game.Num()   ? Game[Game.Num() / 2]     : 0.0;
	const double RenderMedian = Render.Num() ? Render[Render.Num() / 2] : 0.0;
	Q.bRenderBound = RenderMedian > GameMedian;

	// 아래 기준을 넘으면 그 실행은 리포트에 쓰기 전에 원인을 찾아야 한다.
	if (Q.MeasuredSeconds < 5.0)
	{
		Q.Warnings.Add(FString::Printf(
			TEXT("측정 창이 %.2f초로 짧다. 5초 미만이면 클럭이 안정되기 전에 끝난다"),
			Q.MeasuredSeconds));
	}
	if (Q.HitchRatio > 0.01)
	{
		Q.Warnings.Add(FString::Printf(
			TEXT("히치 %.1f%% (%d 프레임). 백그라운드 프로세스와 코어 고정을 확인한다"),
			Q.HitchRatio * 100.0, Q.HitchCount));
	}
	if (Q.bRenderBound)
	{
		Q.Warnings.Add(FString::Printf(
			TEXT("렌더 스레드(%.3fms)가 게임 스레드(%.3fms)보다 크다. CPU 항목이면 -nullrhi 로 돌린다"),
			RenderMedian, GameMedian));
	}
	if (FrameSamplesMs.Num() < 300)
	{
		Q.Warnings.Add(FString::Printf(
			TEXT("샘플이 %d 프레임뿐이다. 분포를 보기에 부족하다"), FrameSamplesMs.Num()));
	}
	return Q;
}

void ABenchRunner::LogSummary(const FBenchQuality& Quality) const
{
	TArray<double> Frame = FrameSamplesMs;
	TArray<double> Game  = GameThreadSamplesMs;
	TArray<double> Render = RenderThreadSamplesMs;
	TArray<double> Gpu   = GpuSamplesMs;
	const FBenchStats F = FBenchStats::FromSamples(Frame);
	const FBenchStats G = FBenchStats::FromSamples(Game);
	const FBenchStats R = FBenchStats::FromSamples(Render);
	const FBenchStats P = FBenchStats::FromSamples(Gpu);

	UE_LOG(LogBench, Display, TEXT("[phase] 측정 종료. %d 프레임 / %.2f초 / 평균 %.0f fps"),
		F.Count, Quality.MeasuredSeconds, Quality.AverageFps);
	UE_LOG(LogBench, Display,
		TEXT("[stat] game median=%.3f p95=%.3f | frame median=%.3f p95=%.3f | render median=%.3f | gpu median=%.3f"),
		G.Median, G.P95, F.Median, F.P95, R.Median, P.Median);

	if (Quality.Warnings.Num() == 0)
	{
		UE_LOG(LogBench, Display, TEXT("[quality] 경고 없음"));
	}
	else
	{
		for (const FString& Warning : Quality.Warnings)
		{
			UE_LOG(LogBench, Warning, TEXT("[quality] %s"), *Warning);
		}
	}
	UE_LOG(LogBench, Display, TEXT("=== MythBench 종료 · 결과 %s ==="), *Spec.OutDir);
}

void ABenchRunner::WriteResults(const FBenchQuality& Quality)
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
	FFileHelper::SaveStringToFile(Raw, *FPaths::Combine(OutDir, TEXT("frames.csv")),
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);

	const FBenchStats Frame    = FBenchStats::FromSamples(FrameSamplesMs);
	const FBenchStats ScenarioS= FBenchStats::FromSamples(ScenarioSamplesMs);
	const FBenchStats GameT    = FBenchStats::FromSamples(GameThreadSamplesMs);
	const FBenchStats RenderT  = FBenchStats::FromSamples(RenderThreadSamplesMs);
	const FBenchStats Gpu      = FBenchStats::FromSamples(GpuSamplesMs);

	FString WarningsJson;
	for (const FString& Warning : Quality.Warnings)
	{
		if (!WarningsJson.IsEmpty())
		{
			WarningsJson += TEXT(", ");
		}
		WarningsJson += FString::Printf(TEXT("\"%s\""), *BenchJson::Escape(Warning));
	}

	const FString Summary = FString::Printf(
		TEXT("{\n")
		TEXT("  \"scenario\": \"%s\",\n")
		TEXT("  \"param_n\": %d,\n")
		TEXT("  \"param_extra\": \"%s\",\n")
		TEXT("  \"repeat_index\": %d,\n")
		TEXT("  \"warmup_seconds\": %.3f,\n")
		TEXT("  \"measured_seconds\": %.3f,\n")
		TEXT("  \"measured_frames\": %d,\n")
		TEXT("  \"average_fps\": %.1f,\n")
		TEXT("  \"hitch_count\": %d,\n")
		TEXT("  \"hitch_ratio\": %.5f,\n")
		TEXT("  \"render_bound\": %s,\n")
		TEXT("  \"warnings\": [%s],\n")
		TEXT("  \"frame_ms\":       { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"scenario_ms\":    { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"game_ms\":        { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"render_ms\":      { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"gpu_ms\":         { \"median\": %.4f, \"p95\": %.4f, \"min\": %.4f, \"max\": %.4f },\n")
		TEXT("  \"environment\": %s")
		TEXT("}\n"),
		*BenchJson::Escape(Spec.Scenario), Spec.N,
		*BenchJson::Escape(Scenario->GetParamExtra()), Spec.RepeatIndex,
		MeasureStartSeconds - StartSeconds, Quality.MeasuredSeconds, Frame.Count,
		Quality.AverageFps, Quality.HitchCount, Quality.HitchRatio,
		Quality.bRenderBound ? TEXT("true") : TEXT("false"), *WarningsJson,
		Frame.Median, Frame.P95, Frame.Min, Frame.Max,
		ScenarioS.Median, ScenarioS.P95, ScenarioS.Min, ScenarioS.Max,
		GameT.Median, GameT.P95, GameT.Min, GameT.Max,
		RenderT.Median, RenderT.P95, RenderT.Min, RenderT.Max,
		Gpu.Median, Gpu.P95, Gpu.Min, Gpu.Max,
		*Environment.ToJson());

	FFileHelper::SaveStringToFile(Summary, *FPaths::Combine(OutDir, TEXT("summary.json")),
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	FFileHelper::SaveStringToFile(Environment.ToJson(), *FPaths::Combine(OutDir, TEXT("env.json")),
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
