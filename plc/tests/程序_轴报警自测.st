(* Offline adapter behavior with mock MC blocks. Never run on physical axes. *)
PROGRAM PRG_AxisAlarmTest
VAR
    Step : UINT;
    Passed : UINT;
    Failed : UINT;
    Done : BOOL;
    DummyAxis : AXIS_REF_SM3;
    Motion : FB_AxisUnderTest;
    Fault : FB_AxisUnderTest;
    InvalidRead : FB_AxisUnderTest;
    FailedRead : FB_AxisUnderTest;
    Bus : FB_AxisUnderTest;
    Emergency : FB_AxisUnderTest;
    Pulse : FB_AxisUnderTest;
    States : ARRAY[0..5] OF 结构体_轴状态;
    PulseState : 结构体_轴状态;
    LimitStop : FB_AxisUnderTest;
    SoftwareStop : FB_AxisUnderTest;
    LimitState : 结构体_轴状态;
    SoftwareState : 结构体_轴状态;
END_VAR

CASE Step OF
0:
    Motion(Axis := DummyAxis, State := States[0], Code := 0);
    Fault(Axis := DummyAxis, State := States[1], Code := 0);
    InvalidRead(Axis := DummyAxis, State := States[2], Code := 0);
    FailedRead(Axis := DummyAxis, State := States[3], Code := 0);
    Bus(Axis := DummyAxis, State := States[4], Code := 0, BusOperational := FALSE);
    Emergency(Axis := DummyAxis, State := States[5], Code := 0);
    Pulse.fb读位置.Valid := FALSE;
    Pulse.fb读速度.Valid := FALSE;
    Pulse(Axis := DummyAxis, State := PulseState, Code := 0, OpenLoop := TRUE);
    IF PulseState.b在线 AND NOT PulseState.b已使能 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    IF States[0].b在线 AND NOT States[4].b在线 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Step := 1;
1:
    Motion(Axis := DummyAxis, State := States[0], Code := 20, Sequence := 1);
    Step := 2;
2:
    Motion(Axis := DummyAxis, State := States[0], Code := 24, Sequence := 2,
        Speed := 5000, Acceleration := 2000, Deceleration := 3000, StopDeceleration := 0);
    IF Motion.lr锁定停止减速度 = 3.0 AND States[0].b正向点动 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Fault.fb读状态.Errorstop := TRUE;
    Fault.fb读轴错.AxisErrorID := DWORD#16#1234;
    Fault(Axis := DummyAxis, State := States[1], Code := 0);
    IF (States[1].w错误码 = 1104) AND (States[1].dw驱动错误 = DWORD#16#1234) THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    IF NOT Fault.fb上电.Enable THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    InvalidRead.fb读状态.Errorstop := TRUE;
    InvalidRead.fb读轴错.Valid := FALSE;
    InvalidRead.fb读轴错.AxisErrorID := DWORD#16#1234;
    InvalidRead(Axis := DummyAxis, State := States[2], Code := 0);
    IF (States[2].w错误码 = 1104) AND (States[2].dw驱动错误 = 0) THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    FailedRead.fb读状态.Errorstop := TRUE;
    FailedRead.fb读轴错.Valid := FALSE;
    FailedRead.fb读轴错.Error := TRUE;
    FailedRead.fb读轴错.ErrorID := DWORD#16#55;
    FailedRead.fb读轴错.AxisErrorID := DWORD#16#1234;
    FailedRead(Axis := DummyAxis, State := States[3], Code := 0);
    IF (States[3].w错误码 = 1104) AND (States[3].dw驱动错误 = DWORD#16#55) THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Bus(Axis := DummyAxis, State := States[4], Code := 20, BusOperational := FALSE);
    IF NOT States[4].b在线 AND NOT States[4].b已使能 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Emergency(Axis := DummyAxis, State := States[5], Code := 20, HardEstop := TRUE);
    IF (States[5].w错误码 = 1103) AND NOT States[5].b已使能 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Step := 3;
3:
    Fault(Axis := DummyAxis, State := States[1], Code := 23, Sequence := 3);
    IF Fault.fb复位.Execute AND NOT Fault.fb上电.Enable THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    LimitStop(Axis := DummyAxis, State := LimitState, Code := 0);
    SoftwareStop(Axis := DummyAxis, State := SoftwareState, Code := 0);
    Step := 4;
4:
    LimitStop(Axis := DummyAxis, State := LimitState, Code := 20, Sequence := 1);
    SoftwareStop(Axis := DummyAxis, State := SoftwareState, Code := 20, Sequence := 1);
    Fault.fb复位.Done := TRUE;
    Fault.fb读状态.Errorstop := FALSE;
    Fault(Axis := DummyAxis, State := States[1], Code := 0);
    IF NOT Fault.b请求上电 AND NOT States[1].b已使能 AND NOT States[1].b故障 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Step := 5;
5:
    LimitStop(Axis := DummyAxis, State := LimitState, Code := 27, Sequence := 2,
        Target := 10000, Speed := 5000, Acceleration := 2000, Deceleration := 3000);
    SoftwareStop(Axis := DummyAxis, State := SoftwareState, Code := 27, Sequence := 2,
        Target := 10000, Speed := 5000, Acceleration := 2000, Deceleration := 3000);
    Step := 6;
6:
    LimitStop.fb读状态.StandStill := FALSE;
    LimitStop.fb读状态.DiscreteMotion := TRUE;
    LimitStop.fb读速度.Velocity := 1.0;
    LimitStop(Axis := DummyAxis, State := LimitState, Code := 0, PositiveLimit := TRUE);
    IF LimitStop.fb停止.Execute AND NOT LimitStop.b执行运动 AND (LimitStop.w激活命令 = 0) THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    SoftwareStop.fb读状态.StandStill := FALSE;
    SoftwareStop.fb读状态.DiscreteMotion := TRUE;
    SoftwareStop.fb读速度.Velocity := 1.0;
    SoftwareStop.fb读位置.Position := LREAL#3000000; (* conversion fault while physically moving *)
    SoftwareStop(Axis := DummyAxis, State := SoftwareState, Code := 0);
    (* Position invalid prevents MC_Stop: power must be removed rather than leave motion enabled. *)
    IF SoftwareState.b故障 AND NOT SoftwareStop.b请求上电 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Step := 7;
7:
    (* 软件报警本身不能阻止有效驱动制动。 *)
    LimitState.b故障 := TRUE;
    LimitStop(Axis := DummyAxis, State := LimitState, Code := 0);
    IF LimitStop.fb停止.Execute AND LimitStop.b请求上电 THEN Passed := Passed + 1;
    ELSE Failed := Failed + 1; END_IF;
    Done := TRUE;
    Step := 8;
END_CASE;
END_PROGRAM
