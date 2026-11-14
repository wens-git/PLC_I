(* 单任务调用。输入为真实传感器，经调用者按存在性与极性归一。
   Token是内部UDINT请求号；连续扫描Execute=TRUE的新Token也可靠受理。
   CancelMode=1撤销完成资格并保持夹持输出（类型3关闭破真空），2撤销全部输出。
   本软件不是物理安全回路。 *)
FUNCTION_BLOCK 功能块_气缸
VAR_INPUT
    Execute : BOOL;
    Token : UDINT;
    Code : WORD;
    SensorWork : BOOL;
    SensorOrigin : BOOL;
    HasWorkSensor : BOOL := TRUE;
    HasOriginSensor : BOOL := TRUE;
    DelayMs : WORD;
    HomeDelayMs : WORD;
    TimeoutMs : WORD;
    HardEstop : BOOL;
    CancelMode : BYTE;
    ValveType : BYTE;
END_VAR
VAR_OUTPUT
    WorkOutput : BOOL;
    OriginOutput : BOOL;
    Moving : BOOL;
    Fault : BOOL;
    AtWork : BOOL;
    AtOrigin : BOOL;
    Error : WORD;
    DoneToken : UDINT;
END_VAR
VAR
    tmr动点滤波 : TON;
    tmr原点滤波 : TON;
    tmr运动 : TON;
    udi上次请求 : UDINT;
    udi活动请求 : UDINT;
    b新请求 : BOOL;
    b配置有效 : BOOL;
    b冲突 : BOOL;
    b取消 : BOOL;
    i目标侧 : INT;
    by锁定阀型 : BYTE;
    w锁定动点延时 : WORD;
    w锁定原点延时 : WORD;
    w锁定超时 : WORD;
    b锁定动点传感器 : BOOL;
    b锁定原点传感器 : BOOL;
END_VAR
b新请求 := Execute AND (Token <> 0) AND (Token <> udi上次请求);
IF b新请求 THEN udi上次请求 := Token; END_IF;
b配置有效 := (TimeoutMs > 0) AND (DelayMs < TimeoutMs) AND (HomeDelayMs < TimeoutMs)
    AND (ValveType <= 3) AND (HasWorkSensor OR (DelayMs > 0))
    AND (HasOriginSensor OR (HomeDelayMs > 0));
b冲突 := HasWorkSensor AND HasOriginSensor AND SensorWork AND SensorOrigin;
IF b新请求 AND (Code = 42) AND NOT HardEstop AND b配置有效 AND NOT b冲突 THEN
    Fault := FALSE; Error := 0;
END_IF;
IF HardEstop THEN Fault := TRUE; Error := 2103;
ELSIF NOT b配置有效 THEN Fault := TRUE; Error := 2131;
ELSIF b冲突 THEN Fault := TRUE; Error := 2110;
ELSIF (udi活动请求 <> 0) AND (DoneToken = 0) AND NOT (b新请求 AND (Code = 42))
    AND ((ValveType <> by锁定阀型)
    OR (DelayMs <> w锁定动点延时) OR (HomeDelayMs <> w锁定原点延时)
    OR (TimeoutMs <> w锁定超时) OR (HasWorkSensor <> b锁定动点传感器)
    OR (HasOriginSensor <> b锁定原点传感器)) THEN
    Fault := TRUE; Error := 2131;
END_IF;
b取消 := HardEstop OR Fault OR (CancelMode <> 0) OR (b新请求 AND (Code = 42));
IF b取消 THEN
    udi活动请求 := 0; DoneToken := 0; i目标侧 := 0; Moving := FALSE;
    IF HardEstop OR Fault OR (CancelMode = 2) OR (b新请求 AND (Code = 42)) THEN
        WorkOutput := FALSE; OriginOutput := FALSE;
    ELSIF ValveType = 3 THEN
        OriginOutput := FALSE;
    END_IF;
ELSIF b新请求 AND ((Code = 40) OR (Code = 41)) THEN
    udi活动请求 := Token; DoneToken := 0;
    IF Code = 40 THEN i目标侧 := 1; ELSE i目标侧 := 2; END_IF;
    by锁定阀型 := ValveType;
    w锁定动点延时 := DelayMs; w锁定原点延时 := HomeDelayMs; w锁定超时 := TimeoutMs;
    b锁定动点传感器 := HasWorkSensor; b锁定原点传感器 := HasOriginSensor;
    WorkOutput := i目标侧 = 1;
    OriginOutput := (i目标侧 = 2) AND ((ValveType = 1) OR (ValveType = 3));
END_IF;
(* 重置定时器后，同一扫描即开始新请求计时，包括单线圈无输出的回原动作。 *)
IF b新请求 OR b取消 THEN
    tmr动点滤波(IN := FALSE, PT := WORD_TO_TIME(DelayMs));
    tmr原点滤波(IN := FALSE, PT := WORD_TO_TIME(HomeDelayMs));
    tmr运动(IN := FALSE, PT := WORD_TO_TIME(TimeoutMs));
END_IF;
tmr动点滤波(IN := NOT b取消 AND ((HasWorkSensor AND SensorWork)
    OR (NOT HasWorkSensor AND (i目标侧 = 1) AND (udi活动请求 <> 0))), PT := WORD_TO_TIME(DelayMs));
tmr原点滤波(IN := NOT b取消 AND ((HasOriginSensor AND SensorOrigin)
    OR (NOT HasOriginSensor AND (i目标侧 = 2) AND (udi活动请求 <> 0))), PT := WORD_TO_TIME(HomeDelayMs));
AtWork := NOT b取消 AND tmr动点滤波.Q AND (NOT HasWorkSensor OR SensorWork);
AtOrigin := NOT b取消 AND tmr原点滤波.Q AND (NOT HasOriginSensor OR SensorOrigin);
(* 无感完成是本次请求的锁存估算，完成后修改延时不能使其闪断。 *)
IF NOT b取消 AND (DoneToken <> 0) THEN
    IF NOT HasWorkSensor THEN AtWork := i目标侧 = 1; END_IF;
    IF NOT HasOriginSensor THEN AtOrigin := i目标侧 = 2; END_IF;
END_IF;
Moving := NOT b取消 AND (udi活动请求 <> 0) AND (DoneToken = 0);
(* 总超时覆盖整个动作；同时到期时超时优先。 *)
tmr运动(IN := Moving, PT := WORD_TO_TIME(TimeoutMs));
IF tmr运动.Q THEN
    Fault := TRUE; Error := 2140; DoneToken := 0; udi活动请求 := 0; i目标侧 := 0;
    Moving := FALSE; WorkOutput := FALSE; OriginOutput := FALSE;
    AtWork := FALSE; AtOrigin := FALSE;
ELSIF Moving AND (((i目标侧 = 1) AND AtWork) OR ((i目标侧 = 2) AND AtOrigin)) THEN
    DoneToken := udi活动请求; Moving := FALSE;
    IF (ValveType = 3) AND (i目标侧 = 2) THEN OriginOutput := FALSE; END_IF;
END_IF;
END_FUNCTION_BLOCK
