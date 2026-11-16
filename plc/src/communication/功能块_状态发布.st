(* Owns publication cadence, uptime, heartbeat, snapshot and binding epochs.
   Runtime/Store are read live through references; no full-state cache exists.
   Only this FB writes Published, after server command and stop arbitration. *)
FUNCTION_BLOCK 功能块_状态发布
VAR_INPUT
    Communication : 结构体_通信状态;
    Diagnostics : 结构体_诊断摘要;
END_VAR
VAR_IN_OUT
    Runtime : 结构体_运行时;
    Published : 类型_发布区;
END_VAR
VAR
    w快照纪元 : WORD;
    wPLC心跳 : WORD;
    udi运行时间 : UDINT;
    tmr心跳 : TON;
    tmr发布 : TON;
    tmr运行时间 : TON;
    b首次发布 : BOOL := TRUE;
    lw气缸在线 : LWORD;
    (* Axis permit bit n <-> PermitCodes[n]; bit 12 stays 0. *)
    aw许可码 : ARRAY[0..11] OF WORD := [20,21,22,23,24,25,27,28,29,30,31,50];
    w许可结果 : WORD;
    w全局许可 : WORD;
    w系统字 : WORD;
    w摘要 : WORD;
    i循环 : UINT;
    i子循环 : UINT;
    ui基址 : UINT;
    ui输入容量 : UINT;
    ui输出容量 : UINT;
    w当前绑定纪元 : WORD := 全局变量_绑定.w绑定纪元;
    lw上次绑定气缸 : LWORD;
    w上次绑定轴 : WORD;
    b绑定已初始化 : BOOL;
END_VAR

tmr心跳(IN := NOT tmr心跳.Q, PT := T#200ms);
IF tmr心跳.Q THEN wPLC心跳 := wPLC心跳 + 1; END_IF;
tmr运行时间(IN := NOT tmr运行时间.Q, PT := T#1s);
IF tmr运行时间.Q THEN udi运行时间 := udi运行时间 + 1; END_IF;
(* Nine FC04 requests take about 180ms on the target. Keep a stable
   publication window; motion, permits and watchdogs still run every scan. *)
tmr发布(IN := NOT tmr发布.Q, PT := T#300ms);
IF b首次发布 OR tmr发布.Q THEN
    b首次发布 := FALSE;
    w快照纪元 := w快照纪元 + 1;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_SNAPSHOT_EPOCH_OFFSET] := w快照纪元;
    FOR i循环 := 0 TO XJV1_INPUT_WORDS - 1 DO
        IF i循环 <> XJV1_STATUS_BASE + XJV1_STATUS_SNAPSHOT_EPOCH_OFFSET THEN Published[i循环] := 0; END_IF;
    END_FOR;
    Published[XJV1_STATUS_BASE] := XJV1_SIGNATURE_HI;
    Published[XJV1_STATUS_BASE + 1] := XJV1_SIGNATURE_LO;
    Published[XJV1_STATUS_BASE + 2] := wPLC心跳;
    Published[XJV1_STATUS_BASE + 3] := Communication.w应答序列;
    Published[XJV1_STATUS_BASE + 4] := Communication.w应答结果;
    Published[XJV1_STATUS_BASE + 5] := Communication.w应答对象;
    Published[XJV1_STATUS_BASE + 6] := Communication.w应答纪元;
    w系统字 := 0;
    IF Communication.bHMI在线 THEN w系统字 := w系统字 OR 1; END_IF;
    IF Runtime.b手动 THEN w系统字 := w系统字 OR 2; END_IF;
    IF Runtime.b运行 THEN w系统字 := w系统字 OR 4; END_IF;
    IF Runtime.b复位中 THEN w系统字 := w系统字 OR 8; END_IF;
    IF Runtime.b硬急停 OR Runtime.b软急停 THEN w系统字 := w系统字 OR 16; END_IF;
    IF Diagnostics.w首报警对象 <> 0 THEN w系统字 := w系统字 OR 32; END_IF;
    IF 全局变量_保持区.Store.b已确认 THEN w系统字 := w系统字 OR 64; END_IF;
    IF Runtime.b待复位 THEN w系统字 := w系统字 OR 256; END_IF;
    IF Runtime.b软急停 THEN w系统字 := w系统字 OR 512; END_IF;
    IF Runtime.b暂停 THEN w系统字 := w系统字 OR 1024; END_IF;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_SYSTEM_OFFSET] := w系统字;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_CAPACITY_OFFSET] := 16#3610;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_AXIS_BOUND_OFFSET] := w已绑定轴;
    lw气缸在线 := 0;
    FOR i循环 := 0 TO 53 DO
        IF ((lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0)
            AND ab气缸映射有效[i循环] AND ab气缸模块就绪[i循环] THEN
            lw气缸在线 := lw气缸在线 OR SHL(LWORD#1, i循环);
        END_IF;
    END_FOR;
    FOR i循环 := 0 TO 3 DO
        Published[XJV1_STATUS_BASE + XJV1_STATUS_CYLINDER_BOUND_OFFSET + i循环] :=
            LWORD_TO_WORD(SHR(lw已绑定气缸, (3 - i循环) * 16));
        Published[XJV1_STATUS_BASE + XJV1_STATUS_CYLINDER_ONLINE_OFFSET + i循环] :=
            LWORD_TO_WORD(SHR(lw气缸在线, (3 - i循环) * 16));
    END_FOR;
    w全局许可 := 0;
    FOR i循环 := 0 TO 15 DO
        ui基址 := XJV1_AXIS_CONFIG_BASE + i循环 * XJV1_AXIS_CONFIG_STRIDE;
        FOR i子循环 := 0 TO 15 DO Published[ui基址 + i子循环] := 全局变量_保持区.Store.aw轴配置[i循环, i子循环]; END_FOR;
        ui基址 := XJV1_AXIS_LIVE_BASE + i循环 * XJV1_AXIS_LIVE_STRIDE;
        IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
            IF Runtime.ast轴[i循环].b在线 THEN
                Published[XJV1_STATUS_BASE + XJV1_STATUS_AXIS_ONLINE_OFFSET] :=
                    Published[XJV1_STATUS_BASE + XJV1_STATUS_AXIS_ONLINE_OFFSET] OR SHL(WORD#1, i循环);
            END_IF;
            w摘要 := 0;
            IF Runtime.ast轴[i循环].b已使能 THEN w摘要 := w摘要 OR 1; END_IF;
            IF Runtime.ast轴[i循环].b运动中 THEN w摘要 := w摘要 OR 2; END_IF;
            IF Runtime.ast轴[i循环].b已回原 THEN w摘要 := w摘要 OR 4; END_IF;
            IF Runtime.ast轴[i循环].b故障 THEN w摘要 := w摘要 OR 8; END_IF;
            IF Diagnostics.aw限位[i循环] <> 0 THEN w摘要 := w摘要 OR 16; END_IF;
            IF Runtime.ast轴[i循环].b静止 THEN w摘要 := w摘要 OR 32; END_IF;
            IF Runtime.ast轴[i循环].b正向点动 THEN w摘要 := w摘要 OR 64; END_IF;
            IF Runtime.ast轴[i循环].b负向点动 THEN w摘要 := w摘要 OR 128; END_IF;
            Published[XJV1_STATUS_BASE + XJV1_STATUS_AXIS_SUMMARY_OFFSET + i循环] := w摘要;
            Published[ui基址] := DWORD_TO_WORD(SHR(DINT_TO_DWORD(Runtime.ast轴[i循环].di位置), 16));
            Published[ui基址 + 1] := DINT_TO_WORD(Runtime.ast轴[i循环].di位置);
            Published[ui基址 + 2] := DWORD_TO_WORD(SHR(DINT_TO_DWORD(Runtime.ast轴[i循环].di速度), 16));
            Published[ui基址 + 3] := DINT_TO_WORD(Runtime.ast轴[i循环].di速度);
            Published[ui基址 + 4] := DWORD_TO_WORD(SHR(DINT_TO_DWORD(Runtime.ast轴[i循环].di目标), 16));
            Published[ui基址 + 5] := DINT_TO_WORD(Runtime.ast轴[i循环].di目标);
            FOR i子循环 := 0 TO 11 DO
                w许可结果 := 函数_动作许可(Code := aw许可码[i子循环], ObjectWord := 16#0100 OR UINT_TO_WORD(i循环),
                    HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                    Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
                IF w许可结果 = 0 THEN Published[ui基址 + 6] := Published[ui基址 + 6] OR SHL(WORD#1, i子循环); END_IF;
            END_FOR;
            Published[ui基址 + 7] := 函数_动作许可(Code := 27, ObjectWord := 16#0100 OR UINT_TO_WORD(i循环),
                HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
            Published[ui基址 + 8] := Runtime.ast轴[i循环].w错误码;
            Published[ui基址 + 9] := DWORD_TO_WORD(SHR(Runtime.ast轴[i循环].dw驱动错误, 16));
            Published[ui基址 + 10] := DWORD_TO_WORD(Runtime.ast轴[i循环].dw驱动错误);
            Published[ui基址 + 11] := Runtime.ast轴[i循环].w序列;
            Published[ui基址 + 12] := Runtime.ast轴[i循环].w运动结果;
            Published[ui基址 + 13] := Diagnostics.aw限位[i循环];
            IF (Published[ui基址 + 6] AND 1) <> 0 THEN w全局许可 := w全局许可 OR 1; END_IF;
            IF (Published[ui基址 + 6] AND 48) <> 0 THEN w全局许可 := w全局许可 OR 2; END_IF;
            IF (Published[ui基址 + 6] AND 448) <> 0 THEN w全局许可 := w全局许可 OR 4; END_IF;
        ELSE Published[ui基址 + 7] := 4;
        END_IF;
    END_FOR;
    FOR i循环 := 0 TO 53 DO
        ui基址 := XJV1_CYLINDER_CONFIG_BASE + i循环 * XJV1_CYLINDER_CONFIG_STRIDE;
        FOR i子循环 := 0 TO 7 DO Published[ui基址 + i子循环] := 全局变量_保持区.Store.aw气缸配置[i循环, i子循环]; END_FOR;
        ui基址 := XJV1_CYLINDER_LIVE_BASE + i循环 * XJV1_CYLINDER_LIVE_STRIDE;
        IF (lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0 THEN
            w摘要 := 0;
            IF Runtime.ast气缸[i循环].b在动点 THEN w摘要 := w摘要 OR 1; END_IF;
            IF Runtime.ast气缸[i循环].b在原点 THEN w摘要 := w摘要 OR 2; END_IF;
            IF Runtime.ast气缸[i循环].b运动中 THEN w摘要 := w摘要 OR 4; END_IF;
            IF Runtime.ast气缸[i循环].b故障 THEN w摘要 := w摘要 OR 8; END_IF;
            Published[XJV1_STATUS_BASE + XJV1_STATUS_CYLINDER_SUMMARY_OFFSET + i循环] := w摘要;
            Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := 0;
            w许可结果 := 函数_动作许可(Code := 40, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 1; END_IF;
            w许可结果 := 函数_动作许可(Code := 41, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 2; END_IF;
            w许可结果 := 函数_动作许可(Code := 50, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 4; END_IF;
            Published[ui基址 + XJV1_CYLINDER_LIVE_REASON_OFFSET] := 函数_动作许可(Code := 40, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := Communication.bHMI在线, JogBusy := Communication.b点动忙,
                Resetting := Runtime.b复位中, Runtime := Runtime, Store := 全局变量_保持区.Store);
            Published[ui基址 + XJV1_CYLINDER_LIVE_ALARM_OFFSET] := Runtime.ast气缸[i循环].w错误码;
        ELSE
            Published[ui基址 + XJV1_CYLINDER_LIVE_REASON_OFFSET] := 4;
        END_IF;
    END_FOR;
    FOR i循环 := 0 TO 119 DO
        ui基址 := XJV1_POINTS_BASE + i循环 * XJV1_POINTS_STRIDE;
        FOR i子循环 := 0 TO 4 DO Published[ui基址 + i子循环] := 全局变量_保持区.Store.aw点位[i循环, i子循环]; END_FOR;
    END_FOR;
    w许可结果 := 函数_动作许可(Code := 1, ObjectWord := 0, HmiOnline := Communication.bHMI在线,
        JogBusy := Communication.b点动忙, Resetting := Runtime.b复位中,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_REASON_OFFSET] := w许可结果;
    IF w许可结果 = 0 THEN w全局许可 := w全局许可 OR 16; END_IF;
    w许可结果 := 函数_动作许可(Code := 11, ObjectWord := 0, HmiOnline := Communication.bHMI在线,
        JogBusy := Communication.b点动忙, Resetting := Runtime.b复位中,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    IF (w许可结果 = 0) AND Runtime.b软急停 THEN w全局许可 := w全局许可 OR 256; END_IF;
    w许可结果 := 函数_动作许可(Code := 52, ObjectWord := 0, HmiOnline := Communication.bHMI在线,
        JogBusy := Communication.b点动忙, Resetting := Runtime.b复位中,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    IF w许可结果 = 0 THEN w全局许可 := w全局许可 OR 512; END_IF;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_PERMIT_OFFSET] := w全局许可;
    IF w全局许可 <> 0 THEN Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_REASON_OFFSET] := 0; END_IF;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_FIRST_ALARM_OFFSET] := Diagnostics.w首报警;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_FIRST_ALARM_OBJECT_OFFSET] := Diagnostics.w首报警对象;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_ALARM_COUNT_OFFSET] := Diagnostics.w报警数;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_LAST_REJECTION_OFFSET] := Communication.w上次拒绝;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_UPTIME_S_OFFSET] := UDINT_TO_WORD(SHR(udi运行时间, 16));
    Published[XJV1_STATUS_BASE + XJV1_STATUS_UPTIME_S_OFFSET + 1] := UDINT_TO_WORD(udi运行时间);
    IF NOT b绑定已初始化 THEN
        b绑定已初始化 := TRUE;
    ELSIF (lw上次绑定气缸 <> lw已绑定气缸) OR (w上次绑定轴 <> w已绑定轴) THEN
        w当前绑定纪元 := w当前绑定纪元 + 1;
    END_IF;
    lw上次绑定气缸 := lw已绑定气缸;
    w上次绑定轴 := w已绑定轴;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_BINDING_EPOCH_OFFSET] := w当前绑定纪元;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_CONFIG_EPOCH_OFFSET] := Communication.w配置纪元;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_POINT_POOL_OFFSET] := ui点位池容量;
    ui输入容量 := MIN(Runtime.ui输入点数, UINT#128);
    ui输出容量 := MIN(Runtime.ui输出点数, UINT#128);
    Published[XJV1_IO_BASE] := UINT_TO_WORD(ui输入容量);
    Published[XJV1_IO_BASE + 1] := UINT_TO_WORD(ui输出容量);
    FOR i循环 := 0 TO 7 DO
        FOR i子循环 := 0 TO 15 DO
            IF (i循环 * 16 + i子循环 < ui输入容量) AND ((Runtime.aw输入[i循环] AND SHL(WORD#1, i子循环)) <> 0) THEN
                Published[XJV1_IO_BASE + 2 + i循环] := Published[XJV1_IO_BASE + 2 + i循环] OR SHL(WORD#1, i子循环);
            END_IF;
            IF (i循环 * 16 + i子循环 < ui输出容量) AND ((Runtime.aw输出[i循环] AND SHL(WORD#1, i子循环)) <> 0) THEN
                Published[XJV1_IO_BASE + 10 + i循环] := Published[XJV1_IO_BASE + 10 + i循环] OR SHL(WORD#1, i子循环);
            END_IF;
        END_FOR;
    END_FOR;
    w快照纪元 := w快照纪元 + 1;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_SNAPSHOT_EPOCH_OFFSET] := w快照纪元;
END_IF;
END_FUNCTION_BLOCK
