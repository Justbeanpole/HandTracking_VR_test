# HandInteraction

웹캠으로 손을 추적해 언리얼 엔진의 노브(`BP_Knob`)를 돌리는 프로젝트다.

MediaPipe가 손 랜드마크에서 **회전 각도**와 **핀치 비율**을 계산해 OSC로 언리얼에 보내고,
언리얼은 핀치 비율이 임계값 아래로 내려가면 노브를 "잡은" 것으로 판정해 회전을 적용한다.
원래 LeapMotion의 `pinch_strength` 로 하던 그랩 인식을 MediaPipe로 대체한 것이다.

```
[웹캠] → MediaPipe → 각도 + 핀치 ──OSC:8000──▶ [Unreal BP_Knob] ─ 회전
                                  ◀─OSC:8001── grab/release (영점 재설정)
```

---

## 1. 필요한 것

| | 버전 | 비고 |
|---|---|---|
| Unreal Engine | **5.3** | `.uproject` 의 EngineAssociation |
| Ultraleap Tracking 플러그인 | - | **저장소에 없음, 직접 설치** (아래 2-2) |
| Python | **3.10** | 3.11 이상은 mediapipe 0.10.9 와 호환 문제 가능 |
| 웹캠 | - | 1대 (Kinect 없이 동작) |

---

## 2. 설치

### 2-1. 클론

```bash
git clone https://github.com/Justbeanpole/HandTracking_VR_test.git
cd HandTracking_VR_test
```

### 2-2. Ultraleap Tracking 플러그인 설치 ⚠️ 필수

이 플러그인은 용량(600MB+) 때문에 저장소에서 제외했다. **설치하지 않으면 프로젝트를 열 때
"플러그인 없음" 경고가 뜨고, `MainLevel` 에 배치된 `LeapHandsPawn` 참조가 깨진다.**

1. 에픽게임즈 런처 → 마켓플레이스에서 **"Ultraleap Tracking"** 검색 후 무료 설치
2. 엔진에 설치되므로 별도 배치는 필요 없다
   (프로젝트 로컬에 두려면 `Plugins/UltraleapTracking/` 에 배치)

> LeapMotion 장치가 없어도 프로젝트는 열린다. 플러그인 자체가 있어야 `.uproject` 참조가 풀린다.

### 2-3. 파이썬 환경

```bash
python -m venv venv
venv\Scripts\activate          # PowerShell: venv\Scripts\Activate.ps1
pip install opencv-python mediapipe python-osc
```

검증된 조합 (문제가 생기면 이 버전으로 고정):

```
mediapipe      0.10.9
opencv-python  5.0.0.93
python-osc     1.10.2
numpy          2.2.6
```

### 2-4. 첫 빌드

`Binaries/`, `Intermediate/`, `DerivedDataCache/` 는 저장소에 없다. `.uproject` 를 더블클릭하면
언리얼이 자동으로 생성한다. **최초 실행은 셰이더 컴파일 때문에 수 분~수십 분 걸린다.**

---

## 3. 실행

### 순서가 중요하다

**① 파이썬 먼저**

```bash
cd Scripts
python mediapipe_knob_osc.py
```

미리보기 창이 뜨고 좌상단에 `angle` / `pinch` 값이 표시된다. 종료는 **ESC**.

**② 그다음 언리얼**에서 `Content/Levels/MainLevel` 을 열고 Play.

손을 카메라에 비추고 **엄지와 검지를 붙이면** 노브가 잡히고, 손을 돌리면 노브가 따라 돈다.
손가락을 벌리면 놓아진다.

### 웹캠이 안 잡히면

`Scripts/mediapipe_knob_osc.py` 상단의 `CAMERA_INDEX` 를 바꾼다 (기본 `1`).

실제 인덱스를 확인하려면:

```bash
pip install pygrabber
python -c "from pygrabber.dshow_graph import FilterGraph; [print(i,n) for i,n in enumerate(FilterGraph().get_input_devices())]"
```

> ⚠️ Azure Kinect가 PC에 연결돼 있으면 그 컬러 카메라도 UVC 장치로 목록에 섞여 나온다.
> Kinect 인덱스를 웹캠으로 열면 충돌하니 **실제 USB 웹캠 인덱스**를 골라야 한다.

---

## 4. OSC 통신 규격

### Python → Unreal (포트 8000)

주소 `/mediapipe/knob/angle` 에 **float 2개**를 보낸다:

| 인덱스 | 값 | 범위 |
|---|---|---|
| 0 | 회전 각도 | 0 ~ 360 (시작 시점이 0도) |
| 1 | 핀치 비율 | 작을수록 붙음 (붙이면 ~0.25, 펴면 ~0.85) |

핀치 비율은 **엄지끝(4)–검지끝(8) 거리 ÷ 손목(0)–중지MCP(9) 길이** 다.
손 크기로 나누기 때문에 손이 카메라에서 멀어져도 값이 변하지 않는다.

회전 각도는 **손목(0)→중지MCP(9)** 선으로 잰다. 엄지–검지 선을 쓰면 핀치할 때
두 점이 겹쳐 각도가 튀기 때문이다.

### Unreal → Python (포트 8001)

| 주소 | 의미 |
|---|---|
| `/unreal/grab` | 노브를 잡음 → 파이썬이 현재 각도를 0도로 재설정 |
| `/unreal/release` | 놓음 |

`mediapipe_knob_osc.py` 는 송신만 하므로 이 신호를 받지 않는다.
(멀티캠 버전에서만 수신 서버를 띄운다.)

---

## 5. 핀치 임계값 튜닝

**환경마다 값이 다르므로 처음 한 번은 반드시 맞춰야 한다.**

1. `mediapipe_knob_osc.py` 를 실행하고 화면의 `pinch: 0.XX` 를 관찰한다
2. 엄지·검지를 **붙였을 때**와 **폈을 때** 값을 각각 기록한다
3. `BP_Knob` 을 열어 아래 두 변수의 Default Value 를 조정한다
   (My Blueprint → Variables → 변수 선택 → Details → Default Value)

| 변수 | 의미 | 기본값 |
|---|---|---|
| `Grab Threshold` | 핀치 값이 **이 아래**로 내려가면 잡음 | 0.3 |
| `Release Threshold` | 핀치 값이 **이 위**로 올라가면 놓음 | 0.4 |

두 값을 다르게 두는 것은 **히스테리시스** 때문이다. 같은 값이면 임계 근처에서
잡았다 놨다가 초당 수십 번 반복되며 떨린다. **간격을 넉넉히 두는 게 좋다.**

> Default Value 칸이 회색이면 상단 **Compile** 을 한 번 누른다.

### 관련 블루프린트 변수

| 변수 | 타입 | 역할 |
|---|---|---|
| `Current MPAngle` | Float | OSC index 0 (각도) |
| `Prev MPAngle` | Float | 이전 프레임 각도 (델타 계산용) |
| `Pinch Value` | Float | OSC index 1 (핀치) |
| `Is Grabbing` | Boolean | 현재 잡은 상태 |
| `Grab Threshold` / `Release Threshold` | Float | 위 참조 |

---

## 6. 저장소에 없는 것

용량 때문에 제외했다. 필요하면 아래에서 구한다.

| 제외 항목 | 크기 | 대응 |
|---|---|---|
| `Plugins/UltraleapTracking/` | 620MB | 마켓플레이스에서 설치 (2-2) |
| `Scripts/` (venv, 데이터셋, 모델) | 6GB | 아래 참조 |
| `Intermediate/` `Binaries/` `Saved/` | 4GB | UE가 자동 생성 |

**예외**: `Scripts/mediapipe_knob_osc.py` 하나만 포함했다. 이게 없으면 노브가 아예 안 돈다.

Kinect 2대 융합 버전, 모델 성능 비교(RTMPose·FreiHAND) 스크립트, 학습 데이터셋은
별도 저장소에 있다: https://github.com/ansgustn/handtracking

---

## 7. 문제 해결

**노브가 전혀 안 움직인다**
- 파이썬 창에 `pinch` 값이 뜨는지 확인 (안 뜨면 손 인식 실패 — 조명·거리 확인)
- 언리얼에서 `Print String` 으로 `Pinch Value` 가 들어오는지 확인
- 방화벽이 UDP 8000 포트를 막고 있지 않은지 확인

**손은 인식되는데 안 잡힌다**
- 임계값 문제다. 5번의 튜닝을 한다. 실제 핀치 값이 0.45까지만 내려가는데
  `Grab Threshold` 가 0.3이면 절대 안 걸린다.

**잡았다 놨다 떨린다**
- `Grab Threshold` 와 `Release Threshold` 간격을 벌린다.

**노브가 두 번 잡히거나 이상하게 움직인다**
- 레벨의 `LeapHandsPawn` 이 LeapMotion으로 그랩을 시도하는 것일 수 있다.
  `BSLowPolyHand` 는 엄지·검지 콜라이더가 겹치면 `BP_Knob` 의 `OnFingerPinched` 를
  직접 호출한다. MediaPipe만 쓸 거라면 아웃라이너에서 `LeapHandsPawn` 을 삭제하거나,
  LeapMotion 장치를 분리한다. (장치가 없으면 손이 안 움직여서 콜라이더도 안 겹친다.)

**프로젝트를 열 때 플러그인 경고가 뜬다**
- Ultraleap Tracking 미설치다. 2-2 참조.
