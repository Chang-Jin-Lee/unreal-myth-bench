// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class MythBench : ModuleRules
{
	public MythBench(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		// RenderCore: GGameThreadTime / GRenderThreadTime / GGPUFrameTime 전역을 읽는다.
		// 입력은 쓰지 않으므로 InputCore / EnhancedInput 은 뺐다.
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "RenderCore" });

		PrivateDependencyModuleNames.AddRange(new string[] {  });

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });
		
		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
