/******************************************************************************
 * Copyright (C) Ultraleap, Inc. 2011-2024.                                   *
 *                                                                            *
 * Use subject to the terms of the Apache License 2.0 available at            *
 * http://www.apache.org/licenses/LICENSE-2.0, or another agreement           *
 * between Ultraleap and you, your company or other organization.             *
 ******************************************************************************/

#include "LeapSubsystem.h"

#include "Runtime/Launch/Resources/Version.h"

#if (ENGINE_MAJOR_VERSION >= 5 && ENGINE_MINOR_VERSION >= 4)
#include "Engine/Engine.h"
#endif


ULeapSubsystem::ULeapSubsystem() 
	: bUseOpenXR(false), bUseDeviceOrigin(false), LeapPawn(nullptr)
{
}

ULeapSubsystem* ULeapSubsystem::Get()
{
	return GEngine->GetEngineSubsystem<ULeapSubsystem>();
}

void ULeapSubsystem::OnGrabCall(AActor* GrabbedActor, USkeletalMeshComponent* HandLeft, USkeletalMeshComponent* HandRight)
{
	if (GrabbedActor != nullptr && HandLeft != nullptr && HandRight != nullptr)
	{
		OnLeapGrab.Broadcast(GrabbedActor, HandLeft, HandRight);
		OnLeapGrabNative.Broadcast(GrabbedActor, HandLeft, HandRight);
	}
}

void ULeapSubsystem::OnReleaseCall(AActor* ReleasedActor, USkeletalMeshComponent* HandLeft, USkeletalMeshComponent* HandRight, FName BoneName)
{
	if (ReleasedActor != nullptr && HandLeft != nullptr && HandRight != nullptr)
	{
		OnLeapRelease.Broadcast(ReleasedActor, HandLeft, HandRight, BoneName);
		OnLeapReleaseNative.Broadcast(ReleasedActor, HandLeft, HandRight, BoneName);
	}
}

void ULeapSubsystem::GrabActionCall(FVector Location, FVector ForwardVec)
{
	OnLeapGrabAction.Broadcast(Location, ForwardVec);
	OnLeapGrabActionNative.Broadcast(Location, ForwardVec);
}

void ULeapSubsystem::LeapTrackingDataCall(const FLeapFrameData& Frame)
{
	if (!IsInGameThread())
	{
		return;
	}
	FLeapFrameData TmpFrame = Frame;
	if (LeapPawn!=nullptr && bUseDeviceOrigin)
	{
		FVector PawnLocation = LeapPawn->GetActorLocation();
		FRotator PawnRot = LeapPawn->GetActorRotation();
		TmpFrame.RotateFrame(PawnRot);
		TmpFrame.TranslateFrame(PawnLocation);
	}
	
	LatestFrameData = TmpFrame;
	
	OnLeapFrameMulti.Broadcast(TmpFrame);
}


void ULeapSubsystem::LeapPinchCall(const FLeapHandData& HandData)
{
	OnLeapPinchMulti.Broadcast(HandData);
}

void ULeapSubsystem::LeapUnPinchCall(const FLeapHandData& HandData)
{
	OnLeapUnPinchMulti.Broadcast(HandData);
}

bool ULeapSubsystem::GetMediaPipeHandLandmarks(EHandType HandType, TArray<FVector>& OutLandmarks)
{
	OutLandmarks.Empty();

	for (const FLeapHandData& Hand : LatestFrameData.Hands)
	{
		if (Hand.HandType == HandType)
		{
			OutLandmarks.SetNum(21);

			// 0: Wrist (손목)
			OutLandmarks[0] = Hand.Arm.NextJoint;

			// Thumb (엄지)
			OutLandmarks[1] = Hand.Thumb.Proximal.PrevJoint;
			OutLandmarks[2] = Hand.Thumb.Proximal.NextJoint;
			OutLandmarks[3] = Hand.Thumb.Intermediate.NextJoint;
			OutLandmarks[4] = Hand.Thumb.Distal.NextJoint;

			// Index (검지)
			OutLandmarks[5] = Hand.Index.Proximal.PrevJoint;
			OutLandmarks[6] = Hand.Index.Proximal.NextJoint;
			OutLandmarks[7] = Hand.Index.Intermediate.NextJoint;
			OutLandmarks[8] = Hand.Index.Distal.NextJoint;

			// Middle (중지)
			OutLandmarks[9] = Hand.Middle.Proximal.PrevJoint;
			OutLandmarks[10] = Hand.Middle.Proximal.NextJoint;
			OutLandmarks[11] = Hand.Middle.Intermediate.NextJoint;
			OutLandmarks[12] = Hand.Middle.Distal.NextJoint;

			// Ring (약지)
			OutLandmarks[13] = Hand.Ring.Proximal.PrevJoint;
			OutLandmarks[14] = Hand.Ring.Proximal.NextJoint;
			OutLandmarks[15] = Hand.Ring.Intermediate.NextJoint;
			OutLandmarks[16] = Hand.Ring.Distal.NextJoint;

			// Pinky (새끼손가락)
			OutLandmarks[17] = Hand.Pinky.Proximal.PrevJoint;
			OutLandmarks[18] = Hand.Pinky.Proximal.NextJoint;
			OutLandmarks[19] = Hand.Pinky.Intermediate.NextJoint;
			OutLandmarks[20] = Hand.Pinky.Distal.NextJoint;

			return true;
		}
	}
	return false;
}

bool ULeapSubsystem::GetUseOpenXR()
{
	return bUseOpenXR;
}

void ULeapSubsystem::SetUseOpenXR(bool UseXR)
{
	bUseOpenXR = UseXR;
}
