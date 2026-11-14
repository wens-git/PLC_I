(* API: installed SM3_Basic 4.10.0.0 LibDoc MC_* declarations.
   Call once per scan, with Code=0 between command pulses. State is not retained.
   The caller owns soft limits, rated limits and bus OP for BusOperational,
   global permissions and jog lease cancellation (Code 26, even Sequence=0).
   HardEstop is ordinary PLC feedback, not a certified safety function.
   Device-tree home search method/direction/speeds must be commissioned. *)
FUNCTION_BLOCK 功能块_轴
VAR_INPUT
    Code : WORD;
    Sequence : WORD;
    Target : DINT;
    Speed : UDINT;
    Acceleration : UDINT;
    Deceleration : UDINT;
    StopDeceleration : UDINT;
    HardEstop : BOOL;
    PositiveLimit : BOOL;
    NegativeLimit : BOOL;
    (* Open-loop pulse hardware has no external presence feedback. *)
    OpenLoop : BOOL;
    (* No external Ready contact. Only bus axes override this with bus OP. *)
    BusOperational : BOOL := TRUE;
END_VAR
VAR_IN_OUT
    Axis : AXIS_REF_SM3;
    State : 结构体_轴状态;
END_VAR
VAR CONSTANT
    (* Original configuration initialization lines 99, 100 and 103. *)
    lr回原位置 : LREAL := 0.0;
    lr位置容差 : LREAL := 0.03;
    lr工程加加速度 : LREAL := 5000.0;
END_VAR
VAR
    fb上电 : MC_Power;
    fb读状态 : MC_ReadStatus;
    fb读位置 : MC_ReadActualPosition;
    fb读速度 : MC_ReadActualVelocity;
    fb读轴错 : MC_ReadAxisError;
    fb运动 : MC_MoveAbsolute;
    fb点动 : MC_Jog;
    fb回原 : MC_Home;
    fb停止 : MC_Stop;
    fb复位 : MC_Reset;
    fb清零 : MC_SetPosition;
    tmr停止 : TON;
    tmr运动 : TON;
    tmr上电 : TON;
    tmr复位 : TON;
    b已初始化 : BOOL;
    w上次命令码 : WORD;
    w上次序列 : WORD;
    b新命令 : BOOL;
    b释放周期 : BOOL;
    b可接收 : BOOL;
    b位置有效 : BOOL;
    b速度有效 : BOOL;
    b反馈有效 : BOOL;
    b物理静止 : BOOL;
    b请求上电 : BOOL;
    b上电过 : BOOL;
    b待去使能 : BOOL;
    b需恢复 : BOOL;
    b正向点动 : BOOL;
    b负向点动 : BOOL;
    b执行运动 : BOOL;
    b执行回原 : BOOL;
    b执行清零 : BOOL;
    b执行复位 : BOOL;
    b复位周期 : BOOL;
    b执行停止 : BOOL;
    b停止可执行 : BOOL;
    b停止用停止块 : BOOL;
    b请求停止 : BOOL;
    i停止阶段 : INT; (* 0 idle, 1 request, 2 decelerating, 3 release Execute *)
    w激活命令 : WORD;
    b待验证 : BOOL;
    lr锁定目标 : LREAL;
    lr锁定速度 : LREAL;
    lr锁定加速度 : LREAL;
    lr锁定减速度 : LREAL;
    lr锁定停止减速度 : LREAL := 1.0;
    lr换算位置 : LREAL;
    lr换算速度 : LREAL;
    w新故障 : WORD;
    dw新驱动错误 : DWORD;
END_VAR

w新故障 := 0;
dw新驱动错误 := 0;
b请求停止 := FALSE;
b新命令 := (Code <> 0) AND ((w上次命令码 = 0) OR (Code <> w上次命令码)
    OR (Sequence <> w上次序列));
IF NOT b已初始化 THEN
    b已初始化 := TRUE;
    b新命令 := FALSE;
    IF (Code = 21) OR (Code = 26) THEN b新命令 := TRUE; END_IF;
    State.b已回原 := FALSE;
    State.b故障 := FALSE;
    State.w错误码 := 0;
    State.dw驱动错误 := 0;
    State.w序列 := 0;
    State.w运动结果 := 0;
    State.di位置 := 0;
    State.di速度 := 0;
    State.di目标 := 0;
END_IF;
w上次命令码 := Code;
IF Code <> 0 THEN w上次序列 := Sequence; END_IF;

fb读状态(Axis := Axis, Enable := TRUE);
fb读位置(Axis := Axis, Enable := TRUE);
fb读速度(Axis := Axis, Enable := TRUE);
fb读轴错(Axis := Axis, Enable := TRUE);
b位置有效 := fb读位置.Valid AND NOT fb读位置.Error;
b速度有效 := fb读速度.Valid AND NOT fb读速度.Error;
lr换算位置 := fb读位置.Position * 1000.0;
lr换算速度 := fb读速度.Velocity * 1000.0;
(* Positive range comparisons reject NaN and infinities before conversion. *)
IF b位置有效 THEN
    IF (lr换算位置 >= LREAL#-2147483648) AND (lr换算位置 <= LREAL#2147483647) THEN
        State.di位置 := LREAL_TO_DINT(lr换算位置);
    ELSE
        b位置有效 := FALSE;
        w新故障 := 1133;
    END_IF;
END_IF;
IF b速度有效 THEN
    IF (lr换算速度 >= LREAL#-2147483648) AND (lr换算速度 <= LREAL#2147483647) THEN
        State.di速度 := LREAL_TO_DINT(lr换算速度);
    ELSE
        b速度有效 := FALSE;
        w新故障 := 1133;
    END_IF;
END_IF;
b反馈有效 := fb读状态.Valid AND NOT fb读状态.Error
    AND b位置有效 AND b速度有效;
State.b在线 := BusOperational AND (OpenLoop OR b反馈有效);
b物理静止 := b反馈有效 AND (fb读状态.StandStill OR fb读状态.Disabled)
    AND (ABS(fb读速度.Velocity) <= LREAL#0.0005);
State.b静止 := b物理静止;
State.w限位 := 0;
IF PositiveLimit THEN State.w限位 := State.w限位 OR 1; END_IF;
IF NegativeLimit THEN State.w限位 := State.w限位 OR 2; END_IF;

IF fb读状态.Error THEN w新故障 := 1110; dw新驱动错误 := TO_DWORD(fb读状态.ErrorID);
ELSIF fb读位置.Error THEN w新故障 := 1111; dw新驱动错误 := TO_DWORD(fb读位置.ErrorID);
ELSIF fb读速度.Error THEN w新故障 := 1112; dw新驱动错误 := TO_DWORD(fb读速度.ErrorID);
END_IF;
IF (b请求上电 OR (w激活命令 <> 0) OR (i停止阶段 <> 0)) AND NOT State.b在线 THEN
    w新故障 := 1101;
END_IF;

b可接收 := NOT b释放周期 AND (i停止阶段 = 0) AND (w激活命令 = 0)
    AND NOT b待验证 AND NOT b执行复位
    AND NOT fb运动.Busy AND NOT fb回原.Busy AND NOT fb清零.Busy
    AND NOT fb复位.Busy AND NOT fb停止.Busy AND NOT fb点动.Busy;
b释放周期 := FALSE;

IF b新命令 THEN
    IF (Code = 21) OR (Code = 26) THEN
        b请求停止 := TRUE;
        (* 只有定位/回原/清零在动时才用 MC_Stop；点动停止只要撤销点动请求，
           开环脉冲轴在无效状态上调用 MC_Stop 会直接进 ErrorStop。 *)
        b停止用停止块 := (w激活命令 = 22) OR (w激活命令 = 27) OR (w激活命令 = 30);
        IF Code = 21 THEN b待去使能 := TRUE; END_IF;
    ELSIF (Code = 23) AND NOT HardEstop AND BusOperational AND b反馈有效
        AND NOT b执行复位 AND NOT fb复位.Busy AND NOT fb复位.Done AND NOT fb复位.Error THEN
        IF fb读状态.Errorstop THEN
            (* 报警态允许先丢掉残留停止阶段/点动，再交给 MC_Reset。 *)
            i停止阶段 := 0;
            b执行停止 := FALSE;
            b正向点动 := FALSE;
            b负向点动 := FALSE;
            b待验证 := FALSE;
            w激活命令 := 0;
            w新故障 := 0;
            b执行复位 := TRUE;
            State.w序列 := Sequence;
            State.w运动结果 := 1;
        ELSIF b物理静止 THEN
            State.b故障 := FALSE;
            State.w错误码 := 0;
            State.dw驱动错误 := 0;
            b需恢复 := FALSE;
            w新故障 := 0;
            State.w序列 := Sequence;
            State.w运动结果 := 2;
            b释放周期 := TRUE;
            (* 复位即重新上电：清故障后自动使能，不再要求单独下发 20。 *)
            b请求上电 := TRUE;
        END_IF;
    ELSIF b可接收 AND State.b在线 AND NOT HardEstop AND NOT State.b故障
        AND NOT b需恢复 AND (w新故障 = 0) THEN
        IF (Code = 20) AND b物理静止 THEN
            b请求上电 := TRUE;
        ELSIF b物理静止 AND fb上电.Status AND b请求上电 THEN
            CASE Code OF
                22:
                    IF (StopDeceleration > 0) AND (StopDeceleration <= UDINT#2147483647)
                        AND NOT PositiveLimit AND NOT NegativeLimit THEN
                        lr锁定停止减速度 := UDINT_TO_LREAL(StopDeceleration) / 1000.0;
                        b执行回原 := TRUE;
                        State.b已回原 := FALSE;
                        lr锁定目标 := lr回原位置;
                        w激活命令 := 22;
                    ELSE w新故障 := 1134;
                    END_IF;
                24, 25, 27:
                    IF (Speed > 0) AND (Speed <= UDINT#2147483647)
                        AND (Acceleration > 0) AND (Acceleration <= UDINT#2147483647)
                        AND (Deceleration > 0) AND (Deceleration <= UDINT#2147483647) THEN
                        lr锁定目标 := DINT_TO_LREAL(Target) / 1000.0;
                        (* 停止减速度缺省时用减速度，不再把整条运动判为 1131。 *)
                        IF (StopDeceleration > 0) AND (StopDeceleration <= UDINT#2147483647) THEN
                            lr锁定停止减速度 := UDINT_TO_LREAL(StopDeceleration) / 1000.0;
                        ELSE
                            lr锁定停止减速度 := UDINT_TO_LREAL(Deceleration) / 1000.0;
                        END_IF;
                        IF ((Code = 24) AND PositiveLimit) OR ((Code = 25) AND NegativeLimit)
                            OR ((Code = 27) AND PositiveLimit AND (lr锁定目标 > fb读位置.Position))
                            OR ((Code = 27) AND NegativeLimit AND (lr锁定目标 < fb读位置.Position)) THEN
                            w新故障 := 1134;
                        ELSE
                            lr锁定速度 := UDINT_TO_LREAL(Speed) / 1000.0;
                            lr锁定加速度 := UDINT_TO_LREAL(Acceleration) / 1000.0;
                            lr锁定减速度 := UDINT_TO_LREAL(Deceleration) / 1000.0;
                            w激活命令 := Code;
                            b正向点动 := Code = 24;
                            b负向点动 := Code = 25;
                            b执行运动 := Code = 27;
                        END_IF;
                    ELSE w新故障 := 1131;
                    END_IF;
                30:
                    b执行清零 := TRUE;
                    State.b已回原 := FALSE;
                    lr锁定目标 := 0.0;
                    w激活命令 := 30;
            END_CASE;
            IF w激活命令 <> 0 THEN
                State.w序列 := Sequence;
                State.w运动结果 := 1;
                IF (w激活命令 = 22) OR (w激活命令 = 30) THEN State.di目标 := 0;
                ELSIF w激活命令 = 27 THEN State.di目标 := Target;
                ELSE State.di目标 := State.di位置;
                END_IF;
            END_IF;
        END_IF;
    END_IF;
END_IF;

(* Home direction belongs to the drive; any hard limit aborts a home search. *)
IF ((PositiveLimit AND (b正向点动 OR ((w激活命令 = 27) AND (lr锁定目标 > fb读位置.Position))
    OR ((w激活命令 <> 0) AND b速度有效 AND (fb读速度.Velocity > 0.0))))
    OR (NegativeLimit AND (b负向点动 OR ((w激活命令 = 27) AND (lr锁定目标 < fb读位置.Position))
    OR ((w激活命令 <> 0) AND b速度有效 AND (fb读速度.Velocity < 0.0))))
    OR ((w激活命令 = 22) AND (PositiveLimit OR NegativeLimit))) THEN
    b请求停止 := TRUE;
END_IF;
tmr运动(IN := ((w激活命令 = 22) OR (w激活命令 = 27) OR (w激活命令 = 30)
    OR b待验证) AND (i停止阶段 = 0), PT := T#180s);
IF tmr运动.Q THEN w新故障 := 1142; END_IF;

IF w新故障 <> 0 THEN
    (* 清故障失败要覆盖原报警，否则现场只看到第一次的 1104/1131，永远看不到 1121。 *)
    IF (NOT State.b故障) OR (w新故障 = 1121) OR (w新故障 = 1145) THEN
        State.w错误码 := w新故障;
        State.dw驱动错误 := dw新驱动错误;
    END_IF;
    State.b故障 := TRUE;
    State.b已回原 := FALSE;
    State.w运动结果 := 3;
    b需恢复 := TRUE;
    b待去使能 := TRUE;
    b请求停止 := TRUE;
END_IF;

IF b请求停止 AND (i停止阶段 = 0) THEN
    i停止阶段 := 1;
    IF (StopDeceleration > 0) AND (StopDeceleration <= UDINT#2147483647) THEN
        lr锁定停止减速度 := UDINT_TO_LREAL(StopDeceleration) / 1000.0;
    ELSE
        (* 缺停止减速度不应变成故障：沿用已锁定值（初始 1.0 mm/s²）。
           配置里加减速为 0 仍由运动分支报 1131。 *)
        IF lr锁定停止减速度 <= 0.0 THEN lr锁定停止减速度 := 1.0; END_IF;
    END_IF;
END_IF;
IF i停止阶段 <> 0 THEN
    b执行运动 := FALSE;
    b执行回原 := FALSE;
    b执行清零 := FALSE;
    b正向点动 := FALSE;
    b负向点动 := FALSE;
    b待验证 := FALSE;
    IF w激活命令 = 22 THEN State.b已回原 := FALSE; END_IF;
    w激活命令 := 0;
    IF NOT State.b故障 AND (State.w运动结果 = 1) THEN State.w运动结果 := 4; END_IF;
END_IF;

IF HardEstop THEN
    b请求上电 := FALSE;
    b待去使能 := FALSE;
    b需恢复 := TRUE;
    b执行运动 := FALSE;
    b执行回原 := FALSE;
    b执行清零 := FALSE;
    b执行复位 := FALSE;
    b正向点动 := FALSE;
    b负向点动 := FALSE;
    b待验证 := FALSE;
    i停止阶段 := 0;
    b执行停止 := FALSE;
    w激活命令 := 0;
    State.b已回原 := FALSE;
    State.b故障 := TRUE;
    State.w错误码 := 1103;
    State.w运动结果 := 3;
END_IF;

IF (i停止阶段 <> 0) AND NOT HardEstop THEN
    IF NOT b反馈有效 OR NOT BusOperational OR fb读状态.Errorstop OR NOT b请求上电 THEN
        b执行停止 := FALSE;
        b请求上电 := FALSE;
        b待去使能 := FALSE;
        i停止阶段 := 0;
        b释放周期 := TRUE;
    ELSIF i停止阶段 = 1 THEN
        IF NOT b停止用停止块 THEN
            (* 点动/空载停止：撤销请求后等轴自然减速到位，不调用 MC_Stop。 *)
            IF b物理静止 THEN i停止阶段 := 3; END_IF;
        ELSIF b物理静止 THEN i停止阶段 := 3;
        ELSE i停止阶段 := 2;
        END_IF;
    END_IF;
END_IF;
b执行停止 := (i停止阶段 = 2) AND b停止用停止块;
tmr停止(IN := i停止阶段 <> 0, PT := T#30s);
IF tmr停止.Q THEN
    b执行停止 := FALSE;
    i停止阶段 := 0;
    b请求上电 := FALSE;
    b待去使能 := FALSE;
    b需恢复 := TRUE;
    State.b故障 := TRUE;
    State.w错误码 := 1140;
    State.w运动结果 := 3;
END_IF;

(* Preserve Errorstop until MC_Reset acknowledges it. MC_Power(FALSE) would
   otherwise overwrite the state with power_off and skip the reset path.
   HardEstop still processes the forced power-off request. *)
b复位周期 := b执行复位;
fb复位(Axis := Axis, Execute := b执行复位);
fb上电(Axis := Axis, Enable := (NOT b执行复位 AND NOT fb读状态.Errorstop) OR HardEstop,
    bRegulatorOn := b请求上电, bDriveStart := b请求上电);
fb运动(Axis := Axis, Execute := b执行运动, Position := lr锁定目标,
    Velocity := lr锁定速度, Acceleration := lr锁定加速度,
    Deceleration := lr锁定减速度, Jerk := lr工程加加速度);
fb回原(Axis := Axis, Execute := b执行回原, Position := lr回原位置);
fb清零(Axis := Axis, Execute := b执行清零, Position := 0.0, Mode := FALSE);
(* 参考原程序：无效轴状态（未使能/报警/ErrorStop/掉线）下不能把 Execute 送进
   MC_Stop / MC_Jog，否则库返回 ErrorID=16#22，会被误报成 1122/1124。
   进入无效态时先撤销 Execute，再由故障/安全路径处理。 *)
b停止可执行 := b执行停止 AND State.b在线 AND NOT State.b故障 AND b反馈有效
    AND fb上电.Status AND NOT fb读状态.Errorstop;
IF b执行停止 AND NOT b停止可执行 THEN
    b执行停止 := FALSE;
    i停止阶段 := 0;
    b释放周期 := TRUE;
END_IF;
IF (NOT State.b在线) OR State.b故障 OR (NOT fb上电.Status) OR fb读状态.Errorstop THEN
    b正向点动 := FALSE;
    b负向点动 := FALSE;
END_IF;
fb点动(Axis := Axis, JogForward := b正向点动, JogBackward := b负向点动,
    Velocity := lr锁定速度, Acceleration := lr锁定加速度,
    Deceleration := lr锁定减速度, Jerk := lr工程加加速度);
fb停止(Axis := Axis, Execute := b停止可执行, Deceleration := lr锁定停止减速度,
    Jerk := lr工程加加速度);

IF (i停止阶段 = 2) AND fb停止.Done THEN
    i停止阶段 := 3;
ELSIF (i停止阶段 = 3) AND NOT fb停止.Busy AND NOT fb停止.Done AND b物理静止 THEN
    i停止阶段 := 0;
    IF b待去使能 THEN b请求上电 := FALSE; END_IF;
    b待去使能 := FALSE;
    b释放周期 := TRUE;
END_IF;
IF b执行复位 AND fb复位.Done THEN
    b执行复位 := FALSE;
    State.b故障 := FALSE;
    State.w错误码 := 0;
    State.dw驱动错误 := 0;
    b需恢复 := FALSE;
    State.w运动结果 := 2;
    b释放周期 := TRUE;
    (* 复位即重新上电：MC_Reset 成功后自动使能，与清故障路径一致。 *)
    b请求上电 := TRUE;
END_IF;
IF ((w激活命令 = 27) AND fb运动.Done) OR ((w激活命令 = 22) AND fb回原.Done)
    OR ((w激活命令 = 30) AND fb清零.Done) THEN
    b执行运动 := FALSE;
    b执行回原 := FALSE;
    b执行清零 := FALSE;
    b待验证 := TRUE;
    b释放周期 := TRUE;
END_IF;
IF b待验证 AND NOT b释放周期 AND b物理静止 AND b位置有效
    AND NOT fb运动.Busy AND NOT fb回原.Busy AND NOT fb清零.Busy
    AND NOT fb运动.Done AND NOT fb回原.Done AND NOT fb清零.Done THEN
    IF ABS(fb读位置.Position - lr锁定目标) <= lr位置容差 THEN
        State.w运动结果 := 2;
        IF w激活命令 = 22 THEN State.b已回原 := TRUE; END_IF;
    ELSE
        State.b故障 := TRUE;
        State.w错误码 := 1143;
        State.w运动结果 := 3;
        b需恢复 := TRUE;
        b请求上电 := FALSE;
    END_IF;
    w激活命令 := 0;
    b待验证 := FALSE;
    b释放周期 := TRUE;
END_IF;

w新故障 := 0;
dw新驱动错误 := 0;
IF NOT b复位周期 AND fb上电.Error THEN w新故障 := 1120; dw新驱动错误 := TO_DWORD(fb上电.ErrorID);
ELSIF b执行复位 AND fb复位.Error THEN w新故障 := 1121; dw新驱动错误 := TO_DWORD(fb复位.ErrorID);
ELSIF b执行停止 AND fb停止.Error THEN w新故障 := 1122; dw新驱动错误 := TO_DWORD(fb停止.ErrorID);
ELSIF (w激活命令 = 22) AND fb回原.Error THEN w新故障 := 1123; dw新驱动错误 := TO_DWORD(fb回原.ErrorID);
ELSIF (b正向点动 OR b负向点动) AND fb点动.Error THEN w新故障 := 1124; dw新驱动错误 := TO_DWORD(fb点动.ErrorID);
ELSIF (w激活命令 = 27) AND fb运动.Error THEN w新故障 := 1125; dw新驱动错误 := TO_DWORD(fb运动.ErrorID);
ELSIF (w激活命令 = 30) AND fb清零.Error THEN w新故障 := 1127; dw新驱动错误 := TO_DWORD(fb清零.ErrorID);
ELSIF ((w激活命令 = 27) AND fb运动.CommandAborted) OR ((w激活命令 = 22) AND fb回原.CommandAborted)
    OR ((b正向点动 OR b负向点动) AND fb点动.CommandAborted) THEN w新故障 := 1126;
END_IF;
(* 具体的功能块错误优先；只有没有其它错误时才把 ErrorStop 归为 1104。 *)
IF (w新故障 = 0) AND fb读状态.Valid AND fb读状态.Errorstop
    AND NOT b执行复位 AND NOT State.b故障 THEN
    w新故障 := 1104;
    (* ErrorID diagnoses the reader; AxisErrorID is the actual axis fault. *)
    IF fb读轴错.Valid AND NOT fb读轴错.Error THEN
        dw新驱动错误 := fb读轴错.AxisErrorID;
    ELSIF fb读轴错.Error THEN
        dw新驱动错误 := TO_DWORD(fb读轴错.ErrorID);
    END_IF;
END_IF;
IF b请求上电 AND b上电过 AND NOT fb上电.Status AND NOT b复位周期 THEN
    w新故障 := 1105;
END_IF;
b上电过 := fb上电.Status;
tmr上电(IN := b请求上电 AND NOT fb上电.Status, PT := T#10s);
IF tmr上电.Q THEN w新故障 := 1144; END_IF;
tmr复位(IN := b执行复位, PT := T#10s);
IF tmr复位.Q THEN w新故障 := 1145; END_IF;
IF w新故障 <> 0 THEN
    (* 清故障失败要覆盖原报警，否则现场只看到第一次的 1104/1131，永远看不到 1121。 *)
    IF (NOT State.b故障) OR (w新故障 = 1121) OR (w新故障 = 1145) THEN
        State.w错误码 := w新故障;
        State.dw驱动错误 := dw新驱动错误;
    END_IF;
    State.b故障 := TRUE;
    State.b已回原 := FALSE;
    State.w运动结果 := 3;
    b需恢复 := TRUE;
    b执行复位 := FALSE;
    b执行运动 := FALSE;
    b执行回原 := FALSE;
    b执行清零 := FALSE;
    b正向点动 := FALSE;
    b负向点动 := FALSE;
    b待验证 := FALSE;
    w激活命令 := 0;
    IF (w新故障 = 1122) OR (w新故障 = 1120) OR (w新故障 = 1144) OR (w新故障 = 1105) THEN
        b请求上电 := FALSE;
        i停止阶段 := 0;
    ELSE
        b待去使能 := TRUE;
        IF i停止阶段 = 0 THEN i停止阶段 := 1; END_IF;
    END_IF;
    b释放周期 := TRUE;
END_IF;
State.b已使能 := State.b在线 AND fb上电.Status AND b请求上电 AND NOT HardEstop;
State.b运动中 := (fb读状态.Valid AND (fb读状态.Stopping OR fb读状态.Homing
    OR fb读状态.DiscreteMotion OR fb读状态.ContinuousMotion OR fb读状态.SynchronizedMotion))
    OR (w激活命令 <> 0) OR (i停止阶段 <> 0) OR fb点动.Busy;
State.b正向点动 := b正向点动 AND State.b已使能;
State.b负向点动 := b负向点动 AND State.b已使能;
State.b可下发 := NOT b释放周期 AND (i停止阶段 = 0) AND (w激活命令 = 0)
    AND NOT b待验证 AND NOT b执行复位
    AND NOT fb运动.Busy AND NOT fb运动.Done
    AND NOT fb回原.Busy AND NOT fb回原.Done
    AND NOT fb清零.Busy AND NOT fb清零.Done
    AND NOT fb复位.Busy AND NOT fb复位.Done AND NOT fb复位.Error
    AND NOT fb停止.Busy AND NOT fb停止.Done AND NOT fb点动.Busy
    AND NOT (b请求上电 AND NOT fb上电.Status);
END_FUNCTION_BLOCK
