// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class MythBench : ModuleRules
{
	public MythBench(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		// 이 모듈은 Public/Private 로 나누지 않은 평면 구조다. 소스가 모듈 루트 기준으로
		// "Bench/..." , "Scenarios/..." 를 include 하므로 모듈 루트를 경로에 넣어준다.
		PublicIncludePaths.Add(ModuleDirectory);
	
		// RenderCore: GGameThreadTime / GRenderThreadTime 전역을 읽는다.
		// RHI: GPU 프레임 시간. 5.8 에서 GGPUFrameTime 은 RHI 내부 전역이라 export 되지 않으므로
		//      DynamicRHI.h 의 RHIGetGPUFrameCycles() 를 쓴다.
		// 입력은 쓰지 않으므로 InputCore / EnhancedInput 은 뺐다.
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "RenderCore", "RHI" });

		PrivateDependencyModuleNames.AddRange(new string[] {  });

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });
		
		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
