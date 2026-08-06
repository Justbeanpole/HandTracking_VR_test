"""
MediaPipe Hands -> OSC streamer for BP_Knob (Unreal Engine).

Tracks one hand on the webcam and sends TWO floats per message:

    index 0 = knob angle in degrees (0..360)
    index 1 = pinch ratio (thumb-index distance / hand size)

BP_Knob reads index 0 for the rotation and compares index 1 against its
Grab/Release thresholds to decide when the knob is being held. Grab used to
come from LeapMotion's pinch_strength; this replaces it.

The rotation angle is measured on the WRIST(0) -> MIDDLE_MCP(9) line, not on
the thumb-index line: pinching collapses thumb and index onto each other, so
an angle taken from those two points would go wild exactly when you grab.
Wrist->middle knuckle stays stable no matter how hard you pinch.

While no hand is visible we keep sending the last angle with an "open" pinch,
so Unreal releases the knob instead of staying stuck in the grabbed state.

Run:  python mediapipe_knob_osc.py
Quit: press ESC in the preview window.
"""

import math

import cv2
import mediapipe as mp
from pythonosc.udp_client import SimpleUDPClient

# ---- Constants (must match BP_Knob) ----
UE_IP = "127.0.0.1"
UE_PORT = 8000
OSC_ADDRESS = "/mediapipe/knob/angle"  # BP_Knob reads the floats here (any address works)
CAMERA_INDEX = 1  # change to 1, 2, ... if the wrong webcam opens

# Landmark indices
WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_MCP = 9

# Pinch value sent when the hand is lost. Must be above BP_Knob's Release
# Threshold so Unreal lets go rather than holding the knob forever.
PINCH_WHEN_NO_HAND = 1.5


def pinch_ratio(lm, w, h):
    """
    Thumb-tip to index-tip distance, normalised by hand size.

    Without the normalisation the raw distance shrinks as the hand moves away
    from the camera, which reads as a pinch and grabs the knob by accident.
    Dividing by the wrist->middle-knuckle length makes the value depth
    independent: roughly 0.2-0.3 when pinched, 0.7+ when open.
    """
    tx, ty = lm[THUMB_TIP].x * w, lm[THUMB_TIP].y * h
    ix, iy = lm[INDEX_TIP].x * w, lm[INDEX_TIP].y * h
    wx, wy = lm[WRIST].x * w, lm[WRIST].y * h
    mx, my = lm[MIDDLE_MCP].x * w, lm[MIDDLE_MCP].y * h

    dist = math.hypot(ix - tx, iy - ty)
    ref = math.hypot(mx - wx, my - wy)
    if ref < 1e-6:
        return None
    return dist / ref


def main():
    client = SimpleUDPClient(UE_IP, UE_PORT)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise SystemExit(f"Could not open webcam index {CAMERA_INDEX}")

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    # --- Angle-tracking state (persists across frames) ---
    prev_raw = None       # previous raw atan2 angle, used for unwrapping
    continuous = 0.0      # unwrapped, continuous angle (no ±180 jumps)
    start_ref = None      # first continuous value -> treated as 0 deg
    last_display = None   # last angle sent, reused while the hand is missing

    with mp_hands.Hands(
        max_num_hands=1,
        model_complexity=0,           # fastest model, fine for a few landmarks
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    ) as hands:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Warning: Failed to read frame from webcam. Checking index or if another app is using it...")
                import time
                time.sleep(1.0)
                continue

            frame = cv2.flip(frame, 1)  # mirror so it feels natural
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)
            h, w = frame.shape[:2]

            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0].landmark
                wrist, mcp = lm[WRIST], lm[MIDDLE_MCP]

                # Image y grows downward; negate dy so counter-clockwise
                # twist (as you see it) = increasing angle.
                dx = mcp.x - wrist.x
                dy = mcp.y - wrist.y
                # Negate so the knob in Unreal turns the SAME direction as
                # the hand (BP_Knob applies the angle with opposite sign).
                raw = -math.degrees(math.atan2(-dy, dx))  # -180..180

                # --- Unwrap into a continuous angle. atan2 wraps at ±180,
                # which made the knob whip a full turn when crossing it.
                # Accumulating the frame-to-frame delta removes that jump. ---
                if prev_raw is None:
                    continuous = raw
                else:
                    delta = raw - prev_raw
                    if delta > 180:
                        delta -= 360
                    elif delta < -180:
                        delta += 360
                    continuous += delta
                prev_raw = raw

                # --- Treat the first reading as 0 deg. ---
                if start_ref is None:
                    start_ref = continuous
                relative = continuous - start_ref  # smooth, unbounded, 0 at start
                display = relative % 360           # 0..360 (0 at start)
                last_display = display

                pinch = pinch_ratio(lm, w, h)
                if pinch is None:
                    pinch = PINCH_WHEN_NO_HAND

                # BP_Knob reads index 0 for the knob rotation (via
                # NormalizeAxis, so 0..360 is fine) and the TextRender label,
                # and index 1 for the Grab/Release threshold test.
                client.send_message(OSC_ADDRESS, [float(display), float(pinch)])

                mp_draw.draw_landmarks(
                    frame,
                    result.multi_hand_landmarks[0],
                    mp_hands.HAND_CONNECTIONS,
                )
                # Highlight the pinch pair so you can see what index 1 measures.
                tp = (int(lm[THUMB_TIP].x * w), int(lm[THUMB_TIP].y * h))
                ip = (int(lm[INDEX_TIP].x * w), int(lm[INDEX_TIP].y * h))
                cv2.line(frame, tp, ip, (0, 255, 255), 2)
                cv2.circle(frame, tp, 6, (0, 255, 255), -1)
                cv2.circle(frame, ip, 6, (0, 255, 255), -1)

                cv2.putText(
                    frame, f"angle: {display:6.1f} deg", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
                )
                cv2.putText(
                    frame, f"pinch: {pinch:5.2f}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2,
                )
            else:
                # Hand lost: hold the angle steady but report an open pinch so
                # Unreal releases instead of staying grabbed forever.
                if last_display is not None:
                    client.send_message(
                        OSC_ADDRESS, [float(last_display), float(PINCH_WHEN_NO_HAND)]
                    )
                cv2.putText(
                    frame, "no hand", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
                )

            cv2.imshow("MediaPipe Knob -> OSC", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
