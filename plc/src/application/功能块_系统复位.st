(* Owns reset phase, committed sequence and timeout. Operation 0 advances once
   before arbitration; 1 accepts reset; 2 cancels immediately during arbitration.
   Start/cancel never advance the timer or phase machine a second time. *)
FUNCTION_BLOCK 功能块_系统复位
VAR_INPUT
    Operation : UINT;
    Sequence : WORD;
END_VAR
VAR_IN_OUT
    Runtime : 结构体_运行时;
END_VAR
VAR_OUTPUT
    Busy : BOOL;
    StopRequested : BOOL;
    Failed : BOOL;
END_VAR
VAR
    ui复位阶段 : UINT;
    w复位序列 : WORD;
    b复位完成 : BOOL;
    b复位失败 : BOOL;
    tmr复位 : TON;
    i循环 : UINT;
END_VAR

StopRequested := FALSE;
Failed := FALSE;
CASE Operation OF
    1:
        Runtime.b待复位 := TRUE;
        w复位序列 := Sequence;
        ui复位阶段 := 1;
        StopRequested := TRUE;
    2:
        ui复位阶段 := 0;
    0:
        tmr复位(IN := ui复位阶段 <> 0, PT := T#30s);
        b复位失败 := Runtime.b硬急停 OR Runtime.b软急停 OR tmr复位.Q;
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                b复位失败 := b复位失败 OR NOT Runtime.ast轴[i循环].b在线;
            END_IF;
        END_FOR;
        IF (ui复位阶段 <> 0) AND b复位失败 THEN
            ui复位阶段 := 0;
            Runtime.b待复位 := TRUE;
            StopRequested := TRUE;
            Failed := TRUE;
        END_IF;
        CASE ui复位阶段 OF
            1:
                b复位完成 := TRUE;
                FOR i循环 := 0 TO 15 DO
                    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                        b复位完成 := b复位完成 AND NOT Runtime.ast轴[i循环].b运动中
                            AND Runtime.ast轴[i循环].b可下发
                            AND (Runtime.ast轴[i循环].b静止 OR (Runtime.ast轴[i循环].b故障 AND (Runtime.ast轴[i循环].di速度 = 0)));
                    END_IF;
                END_FOR;
                IF b复位完成 THEN ui复位阶段 := 2; END_IF;
            2:
                FOR i循环 := 0 TO 15 DO
                    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                        Runtime.aw轴命令[i循环] := 23;
                        Runtime.aw轴序列[i循环] := w复位序列;
                    END_IF;
                END_FOR;
                ui复位阶段 := 3;
            3:
                b复位完成 := TRUE;
                FOR i循环 := 0 TO 15 DO
                    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                        b复位完成 := b复位完成 AND (Runtime.ast轴[i循环].w序列 = w复位序列)
                            AND (Runtime.ast轴[i循环].w运动结果 = 2) AND NOT Runtime.ast轴[i循环].b故障
                            AND Runtime.ast轴[i循环].b静止 AND NOT Runtime.ast轴[i循环].b运动中;
                    END_IF;
                END_FOR;
                IF b复位完成 THEN Runtime.b待复位 := FALSE; ui复位阶段 := 4; END_IF;
            4: ui复位阶段 := 0;
        END_CASE;
END_CASE;
Busy := ui复位阶段 <> 0;
END_FUNCTION_BLOCK
