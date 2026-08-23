#include "Bench/BenchCommon.h"

#include "HAL/PlatformMisc.h"
#include "HAL/PlatformMemory.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/EngineVersion.h"
#include "Misc/Parse.h"
#include "Scalability.h"
#include "HAL/IConsoleManager.h"

FBenchRunSpec FBenchRunSpec::FromCommandLine()
{
	FBenchRunSpec Spec;
	const TCHAR* Cmd = FCommandLine::Get();

	FParse::Value(Cmd, TEXT("bench="),     Spec.Scenario);
	FParse::Value(Cmd, TEXT("N="),         Spec.N);
	FParse::Value(Cmd, TEXT("mode="),      Spec.Mode);
	FParse::Value(Cmd, TEXT("tickgroup="), Spec.TickGroup);
	FParse::Value(Cmd, TEXT("warmup="),    Spec.WarmupFrames);
	FParse::Value(Cmd, TEXT("frames="),    Spec.MeasureFrames);
	FParse::Value(Cmd, TEXT("repeat="),    Spec.RepeatIndex);
	FParse::Value(Cmd, TEXT("machineid="), Spec.MachineId);
	FParse::Value(Cmd, TEXT("out="),       Spec.OutDir);

	Spec.TickGroup = Spec.TickGroup.ToLower();
	return Spec;
}

FString FBenchRunSpec::Describe() const
{
	return FString::Printf(
		TEXT("scenario=%s N=%d mode=%s tickgroup=%s warmup=%d frames=%d repeat=%d"),
		*Scenario, N, Mode.IsEmpty() ? TEXT("-") : *Mode, *TickGroup,
		WarmupFrames, MeasureFrames, RepeatIndex);
}

namespace
{
	FString BuildConfigToString()
	{
		switch (FApp::GetBuildConfiguration())
		{
		case EBuildConfiguration::Debug:       return TEXT("Debug");
		case EBuildConfiguration::DebugGame:   return TEXT("DebugGame");
		case EBuildConfiguration::Development: return TEXT("Development");
		case EBuildConfiguration::Test:        return TEXT("Test");
		case EBuildConfiguration::Shipping:    return TEXT("Shipping");
		default:                               return TEXT("Unknown");
		}
	}

	int32 ReadIntCVar(const TCHAR* Name, int32 Fallback)
	{
		if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			return Var->GetInt();
		}
		return Fallback;
	}
}

FBenchEnvironment FBenchEnvironment::Collect(const FString& InMachineId)
{
	FBenchEnvironment Env;
	Env.MachineId     = InMachineId;
	Env.Cpu           = FPlatformMisc::GetCPUBrand();
	Env.Gpu           = FPlatformMisc::GetPrimaryGPUBrand();
	Env.Os            = FPlatformMisc::GetOSVersion();
	Env.RamGb         = static_cast<int32>(FPlatformMemory::GetPhysicalGBRam());
	Env.EngineVersion = FEngineVersion::Current().ToString();
	Env.BuildConfig   = BuildConfigToString();
	Env.Rhi           = FApp::GetGraphicsRHI();
	Env.bSubstrate    = ReadIntCVar(TEXT("r.Substrate"), 0) != 0;

	const Scalability::FQualityLevels Q = Scalability::GetQualityLevels();
	Env.Scalability.Add(TEXT("view_distance"), Q.ViewDistanceQuality);
	Env.Scalability.Add(TEXT("anti_aliasing"), Q.AntiAliasingQuality);
	Env.Scalability.Add(TEXT("shadow"),        Q.ShadowQuality);
	Env.Scalability.Add(TEXT("post_process"),  Q.PostProcessQuality);
	Env.Scalability.Add(TEXT("texture"),       Q.TextureQuality);
	Env.Scalability.Add(TEXT("effects"),       Q.EffectsQuality);
	Env.Scalability.Add(TEXT("foliage"),       Q.FoliageQuality);
	Env.Scalability.Add(TEXT("shading"),       Q.ShadingQuality);
	return Env;
}

FString FBenchEnvironment::ToJson() const
{
	FString Levels;
	for (const TPair<FString, int32>& Pair : Scalability)
	{
		if (!Levels.IsEmpty())
		{
			Levels += TEXT(", ");
		}
		Levels += FString::Printf(TEXT("\"%s\": %d"), *BenchJson::Escape(Pair.Key), Pair.Value);
	}

	return FString::Printf(
		TEXT("{\n")
		TEXT("  \"machine_id\": \"%s\",\n")
		TEXT("  \"cpu\": \"%s\",\n")
		TEXT("  \"gpu\": \"%s\",\n")
		TEXT("  \"ram_gb\": %d,\n")
		TEXT("  \"os\": \"%s\",\n")
		TEXT("  \"engine_version\": \"%s\",\n")
		TEXT("  \"build_config\": \"%s\",\n")
		TEXT("  \"rhi\": \"%s\",\n")
		TEXT("  \"substrate\": %s,\n")
		TEXT("  \"scalability\": { %s }\n")
		TEXT("}\n"),
		*BenchJson::Escape(MachineId), *BenchJson::Escape(Cpu), *BenchJson::Escape(Gpu),
		RamGb, *BenchJson::Escape(Os), *BenchJson::Escape(EngineVersion),
		*BenchJson::Escape(BuildConfig), *BenchJson::Escape(Rhi),
		bSubstrate ? TEXT("true") : TEXT("false"), *Levels);
}

FBenchStats FBenchStats::FromSamples(TArray<double>& Samples)
{
	FBenchStats Out;
	if (Samples.Num() == 0)
	{
		return Out;
	}

	Samples.Sort();
	Out.Count  = Samples.Num();
	Out.Min    = Samples[0];
	Out.Max    = Samples[Out.Count - 1];
	Out.Median = Samples[Out.Count / 2];

	const int32 P95Index = FMath::Clamp(
		FMath::FloorToInt(0.95f * static_cast<float>(Out.Count - 1)), 0, Out.Count - 1);
	Out.P95 = Samples[P95Index];
	return Out;
}

FString BenchJson::Escape(const FString& In)
{
	FString Out = In;
	Out.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	Out.ReplaceInline(TEXT("\""), TEXT("\\\""));
	return Out;
}
