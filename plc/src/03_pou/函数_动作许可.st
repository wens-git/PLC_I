(* Sole action-permission boundary (SBR_动作许可 role). Structural validation
   belongs to 函数_校验, never duplicate movement predicates in HMI. *)
FUNCTION 函数_动作许可 : WORD
VAR_INPUT
    Code : WORD;
    ObjectWord : WORD;
    HmiOnline : BOOL;
    JogBusy : BOOL;
    Resetting : BOOL;
    b自动请求 : BOOL := FALSE;
    b气缸已受理 : BOOL := FALSE; (* 仅驱动消费时复核当前许可 *)
END_VAR
VAR_IN_OUT
    Runtime : 结构体_运行时;
    Store : 结构体_配置;
END_VAR
VAR
    w类别 : WORD;
    ui对象索引 : UINT;
    ui轴号 : UINT;
    w归属 : WORD;
    b空闲槽 : BOOL;
    b对象已绑定 : BOOL;
    b硬件已接入 : BOOL;
    b是停止 : BOOL;
    b有点位 : BOOL;
    i循环 : UINT;
    i子循环 : UINT;
    di正限位 : DINT;
    di负限位 : DINT;
    di位置 : DINT;
    dw值 : DWORD;
END_VAR

函数_动作许可 := 0;
w类别 := SHR(ObjectWord, 8);
ui对象索引 := WORD_TO_UINT(ObjectWord AND 16#00FF);
IF (w类别 > 3) OR ((w类别 = 0) AND (ui对象索引 <> 0))
OR ((w类别 = 1) AND (ui对象索引 >= 16))
OR ((w类别 = 2) AND (ui对象索引 >= 54))
OR ((w类别 = 3) AND (ui对象索引 >= 120)) THEN
    函数_动作许可 := 15; RETURN;
END_IF;
ui轴号 := ui对象索引;
b空闲槽 := FALSE;
IF w类别 = 3 THEN
    b空闲槽 := Store.aw点位[ui对象索引, 4] = XJV1_POINT_FREE;
    w归属 := SHR(Store.aw点位[ui对象索引, 4], 2) AND WORD#16#000F;
    ui轴号 := WORD_TO_UINT(w归属);
END_IF;
b对象已绑定 := w类别 = 0;
b硬件已接入 := (Runtime.w轴消费掩码 AND w已绑定轴) = w已绑定轴;
IF w类别 = 1 THEN
    b对象已绑定 := (w已绑定轴 AND SHL(WORD#1, ui轴号)) <> 0;
    b硬件已接入 := (Runtime.w轴消费掩码 AND SHL(WORD#1, ui轴号)) <> 0;
ELSIF w类别 = 3 THEN
    (* An owned point is bound exactly when its owner axis is bound; free
       slots are handled separately below. *)
    b对象已绑定 := NOT b空闲槽 AND ((w已绑定轴 AND SHL(WORD#1, ui轴号)) <> 0);
    b硬件已接入 := (Runtime.w轴消费掩码 AND SHL(WORD#1, ui轴号)) <> 0;
ELSIF w类别 = 2 THEN
    b对象已绑定 := (lw已绑定气缸 AND SHL(LWORD#1, ui对象索引)) <> 0;
    b硬件已接入 := ab气缸映射已核验[ui对象索引];
END_IF;
b是停止 := (Code = 9) OR (Code = 10) OR (Code = 26) OR (Code = 42);
(* Stop codes bypass every ordinary gate; an unbound object still rejects 4. *)
IF b是停止 THEN
    IF NOT b对象已绑定 THEN 函数_动作许可 := 4; END_IF;
    RETURN;
END_IF;
IF NOT HmiOnline THEN 函数_动作许可 := 2; RETURN; END_IF;
IF (w类别 = 3) AND b空闲槽 THEN
    (* Free pool slot: only a code-50 claim may address it; the candidate
       owner axis is validated against the binding table in Config. *)
    IF Code <> 50 THEN 函数_动作许可 := 4; RETURN; END_IF;
    IF Runtime.b硬急停 OR Runtime.b软急停 THEN 函数_动作许可 := 3; RETURN; END_IF;
    IF Resetting THEN 函数_动作许可 := 8; RETURN; END_IF;
    IF NOT Runtime.b手动 THEN 函数_动作许可 := 7; RETURN; END_IF;
    RETURN;
END_IF;
IF Code = 53 THEN 函数_动作许可 := 14; RETURN; END_IF;
IF Code = 11 THEN
    (* Clear only the software latch. This does not grant motion permission,
       reset faults, enable an axis, or resume the sequence. *)
    IF Runtime.b硬急停 THEN 函数_动作许可 := 3; END_IF;
    RETURN;
END_IF;
IF Runtime.b硬急停 OR Runtime.b软急停 THEN 函数_动作许可 := 3; RETURN; END_IF;
IF NOT b对象已绑定 THEN 函数_动作许可 := 4; RETURN; END_IF;
IF w类别 = 2 THEN
    IF Resetting THEN 函数_动作许可 := 8; RETURN; END_IF;
    IF Runtime.b暂停 THEN 函数_动作许可 := 7; RETURN; END_IF;
    IF b自动请求 THEN
        IF NOT 全局变量_运行配置.b正式流程已接入 THEN 函数_动作许可 := 12; RETURN; END_IF;
        IF NOT Runtime.b运行 THEN 函数_动作许可 := 7; RETURN; END_IF;
    ELSIF NOT Runtime.b手动 THEN 函数_动作许可 := 7; RETURN;
    END_IF;
    IF (Code <> 40) AND (Code <> 41) AND (Code <> 50) THEN 函数_动作许可 := 14; RETURN; END_IF;
    IF NOT b气缸已受理 AND (全局变量_气缸请求.ast请求[ui对象索引].b忙
        OR Runtime.ast气缸[ui对象索引].b运动中) THEN 函数_动作许可 := 10; RETURN; END_IF;
    IF Code = 50 THEN RETURN; END_IF;
    IF NOT b硬件已接入 THEN 函数_动作许可 := 14; RETURN; END_IF;
    IF NOT ab气缸模块就绪[ui对象索引] THEN 函数_动作许可 := 5; RETURN; END_IF;
    IF Runtime.ast气缸[ui对象索引].b故障 THEN 函数_动作许可 := 17; RETURN; END_IF;
    IF Runtime.b待复位 THEN 函数_动作许可 := 11; RETURN; END_IF;
    IF NOT Store.b已确认 THEN 函数_动作许可 := 14; RETURN; END_IF;
    IF NOT 气缸_配置有效(缸号 := ui对象索引, Store := Store) THEN 函数_动作许可 := 9; END_IF;
    RETURN;
END_IF;
(* 整机启动/暂停/恢复。正式工艺未接入时三条一律拒绝 12，与原程序
   “NOT b正式流程已接入 → 拒绝” 一致；接入后由运行状态机判定模式与暂停，
   这里只做安全与前置条件检查，不复制运行状态机的优先级逻辑。 *)
IF (Code = 2) OR (Code = 3) OR (Code = 4) THEN
    IF NOT 全局变量_运行配置.b正式流程已接入 THEN 函数_动作许可 := 12; RETURN; END_IF;
    IF Code = 2 THEN
        IF Runtime.b待复位 THEN 函数_动作许可 := 14; RETURN; END_IF;
    ELSIF Code = 4 THEN
        IF NOT Runtime.b暂停 THEN 函数_动作许可 := 14; RETURN; END_IF;
    END_IF;
    RETURN;
END_IF;
IF Resetting AND (Code <> 21) THEN 函数_动作许可 := 8; RETURN; END_IF;
IF w类别 = 0 THEN
    IF Code = 1 THEN
        IF NOT b硬件已接入 THEN 函数_动作许可 := 14; RETURN; END_IF;
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                IF NOT Runtime.ast轴[i循环].b在线 THEN 函数_动作许可 := 5; RETURN; END_IF;
            END_IF;
        END_FOR;
    ELSIF Code = 52 THEN
        IF NOT Runtime.b手动 THEN 函数_动作许可 := 7; RETURN; END_IF;
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                IF NOT Runtime.ast轴[i循环].b在线 THEN 函数_动作许可 := 5; RETURN; END_IF;
                IF Runtime.ast轴[i循环].b故障 THEN 函数_动作许可 := 17; RETURN; END_IF;
                IF Runtime.ast轴[i循环].b运动中 OR NOT Runtime.ast轴[i循环].b静止 THEN
                    函数_动作许可 := 10; RETURN;
                END_IF;
                di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(Store.aw轴配置[i循环, 0]), 16) OR WORD_TO_DWORD(Store.aw轴配置[i循环, 1]));
                di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(Store.aw轴配置[i循环, 2]), 16) OR WORD_TO_DWORD(Store.aw轴配置[i循环, 3]));
                IF (Store.aw轴配置[i循环, 14] <> 1) OR (Store.aw轴配置[i循环, 15] <> 0) THEN
                    函数_动作许可 := 20; RETURN;
                END_IF;
                IF di负限位 >= di正限位 THEN 函数_动作许可 := 21; RETURN; END_IF;
                FOR i子循环 := 2 TO 6 DO
                    dw值 := SHL(WORD_TO_DWORD(Store.aw轴配置[i循环, i子循环 * 2]), 16) OR WORD_TO_DWORD(Store.aw轴配置[i循环, i子循环 * 2 + 1]);
                    IF (dw值 = 0) OR (dw值 > DWORD#2147483647) THEN
                        函数_动作许可 := 函数_参数码(i子循环); RETURN;
                    END_IF;
                    IF NOT 函数_额定值(AxisIndex := i循环, Field := i子循环,
                        Value := DWORD_TO_UDINT(dw值)) THEN
                        函数_动作许可 := 函数_参数码(i子循环); RETURN;
                    END_IF;
                END_FOR;
                (* Standby point P0 of axis i is pool slot i by definition. *)
                IF (SHR(Store.aw点位[i循环, 4], 2) AND WORD#16#000F) <> UINT_TO_WORD(i循环)
                OR (Store.aw点位[i循环, 4] AND 3) <> 3 THEN 函数_动作许可 := 18; RETURN; END_IF;
                di位置 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(Store.aw点位[i循环, 0]), 16) OR WORD_TO_DWORD(Store.aw点位[i循环, 1]));
                dw值 := SHL(WORD_TO_DWORD(Store.aw点位[i循环, 2]), 16) OR WORD_TO_DWORD(Store.aw点位[i循环, 3]);
                IF (di位置 < di负限位) OR (di位置 > di正限位) THEN 函数_动作许可 := 26; RETURN; END_IF;
                IF (dw值 = 0) OR (dw值 > DWORD#2147483647) THEN 函数_动作许可 := 28; RETURN; END_IF;
            END_IF;
        END_FOR;
        FOR i循环 := 0 TO 53 DO
            IF (lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0 THEN
                IF NOT 气缸_配置有效(缸号 := i循环, Store := Store) THEN 函数_动作许可 := 9; RETURN; END_IF;
                IF 全局变量_气缸请求.ast请求[i循环].b忙 THEN 函数_动作许可 := 10; RETURN; END_IF;
            END_IF;
        END_FOR;
    ELSE
        函数_动作许可 := 14;
    END_IF;
    RETURN;
END_IF;
IF (Runtime.aw轴命令[ui轴号] <> 0) AND (Code <> 21) THEN
    函数_动作许可 := 10; RETURN;
END_IF;
IF NOT b自动请求 AND 全局变量_轴请求.ast请求[ui轴号].b忙 AND (Code <> 21) THEN
    函数_动作许可 := 10; RETURN;
END_IF;
CASE Code OF
    20, 21, 22, 23, 24, 25, 27, 28, 29, 30, 31, 50: ;
ELSE
    函数_动作许可 := 14; RETURN;
END_CASE;
IF NOT Runtime.ast轴[ui轴号].b在线 THEN 函数_动作许可 := 5; RETURN; END_IF;
(* 写参数（31/50）不动轴，报警期间也允许改；复位 23 与去使能 21 同样放行。 *)
IF Runtime.ast轴[ui轴号].b故障 AND (Code <> 21) AND (Code <> 23)
    AND (Code <> 31) AND (Code <> 50) THEN
    函数_动作许可 := 17; RETURN;
END_IF;
IF b自动请求 THEN
    IF NOT 全局变量_运行配置.b正式流程已接入 THEN 函数_动作许可 := 12; RETURN; END_IF;
    IF NOT Runtime.b运行 OR Runtime.b暂停 THEN 函数_动作许可 := 7; RETURN; END_IF;
    IF Runtime.b待复位 THEN 函数_动作许可 := 11; RETURN; END_IF;
ELSIF NOT Runtime.b手动 AND (Code <> 21) THEN 函数_动作许可 := 7; RETURN;
END_IF;
IF ((Code = 22) OR (Code = 24) OR (Code = 25) OR (Code = 27) OR (Code = 28) OR (Code = 29) OR (Code = 30))
AND NOT Runtime.ast轴[ui轴号].b已使能 THEN 函数_动作许可 := 6; RETURN; END_IF;
(* 清故障在报警态必须可重试：轴停在 ErrorStop 时 b运动中 可能因残留停止阶段为真，
   若因此拒绝 23，现场就永远清不掉。复位本身仍要求 MC_Reset 成功。 *)
IF (Code >= 20) AND (Code <= 30) AND (Code <> 21)
AND NOT Runtime.ast轴[ui轴号].b可下发 THEN
    函数_动作许可 := 10; RETURN;
END_IF;
IF (Runtime.ast轴[ui轴号].b运动中 OR NOT Runtime.ast轴[ui轴号].b静止) AND (Code <> 21) AND (Code <> 23) THEN
    函数_动作许可 := 10; RETURN;
END_IF;
IF (Code = 24) OR (Code = 25) THEN
    IF JogBusy THEN 函数_动作许可 := 10; RETURN; END_IF;
    IF ((Code = 24) AND ((Runtime.ast轴[ui轴号].w限位 AND 5) <> 0))
    OR ((Code = 25) AND ((Runtime.ast轴[ui轴号].w限位 AND 10) <> 0)) THEN
        函数_动作许可 := 17; RETURN;
    END_IF;
END_IF;
IF Code = 29 THEN
    b有点位 := FALSE;
    FOR i循环 := 0 TO 119 DO
        b有点位 := b有点位 OR ((SHR(Store.aw点位[i循环, 4], 2) AND WORD#16#000F) = UINT_TO_WORD(ui轴号)
            AND ((Store.aw点位[i循环, 4] AND 3) = 3));
    END_FOR;
    IF NOT b有点位 THEN 函数_动作许可 := 18; RETURN; END_IF;
END_IF;
IF ((Code >= 20) AND (Code <= 30)) AND NOT b硬件已接入 THEN
    函数_动作许可 := 14; RETURN;
END_IF;
IF (Code = 20) OR (Code = 22) OR (Code = 24) OR (Code = 25)
OR (Code = 27) OR (Code = 28) OR (Code = 29) THEN
    FOR i子循环 := 2 TO 6 DO
        dw值 := SHL(WORD_TO_DWORD(Store.aw轴配置[ui轴号, i子循环 * 2]), 16)
            OR WORD_TO_DWORD(Store.aw轴配置[ui轴号, i子循环 * 2 + 1]);
        IF NOT 函数_额定值(AxisIndex := ui轴号, Field := i子循环,
            Value := DWORD_TO_UDINT(dw值)) THEN
            函数_动作许可 := 函数_参数码(i子循环); RETURN;
        END_IF;
    END_FOR;
END_IF;
END_FUNCTION
