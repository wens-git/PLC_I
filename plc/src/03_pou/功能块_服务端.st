(* One serialized control-task owner: Server -> axis consumers.
   Command is the Holding Register image of the official ModbusTCP slave
   (read-only here). A command is committed when Command[4] (SEQ) changes to a
   nonzero value different from the last consumed SEQ; the host writes SEQ last
   with its own FC06 after every payload write succeeded. The whole block is
   copied once on that scan, so later host writes cannot alter it.
   Published is the Input Register image; only this FB writes it.
   ACK means accepted, never motion complete. Hardware proof belongs to PRG.
   Config records are retained; all leases, pulses, ACKs and resets are volatile. *)
FUNCTION_BLOCK 功能块_服务端
VAR_INPUT
    (* Holding image of the official slave: master-owned, read-only here.
       Passed by value: the FB works on one scan-consistent copy and never
       holds a writable reference to an input channel. *)
    Command : 类型_命令区;
END_VAR
VAR_IN_OUT
    Published : 类型_发布区;
    Runtime : 结构体_运行时;
END_VAR
VAR_OUTPUT
    StopAllRequested : BOOL;
    SoftwareEstopRequested : BOOL;
END_VAR
VAR
    fb看门狗 : 功能块_看门狗;
    fb配置 : 功能块_配置;
    st请求 : 类型_命令区;
    b已初始化 : BOOL;
    w上次序列 : WORD;
    w应答序列 : WORD;
    w应答结果 : WORD;
    w应答对象 : WORD;
    w应答纪元 : WORD;
    w上次拒绝 : WORD;
    w快照纪元 : WORD;
    wPLC心跳 : WORD;
    udi运行时间 : UDINT;
    tmr心跳 : TON;
    tmr发布 : TON;
    tmr运行时间 : TON;
    tmr复位 : TON;
    b首次发布 : BOOL := TRUE;
    b签名有效 : BOOL;
    b起点动脉冲 : BOOL;
    b停点动脉冲 : BOOL;
    w起点动对象 : WORD;
    w起点动序列 : WORD;
    ui点动索引 : UINT;
    ui复位阶段 : UINT;
    w复位序列 : WORD;
    b复位完成 : BOOL;
    b复位失败 : BOOL;
    b安全停止 : BOOL;
    w类别 : WORD;
    ui轴号 : UINT;
    i点位索引 : UINT;
    w校验 : WORD;
    di目标 : DINT;
    li宽目标 : LINT;
    udi速度 : UDINT;
    di正限位 : DINT;
    di负限位 : DINT;
    aw限位 : ARRAY[0..15] OF WORD;
    ab上次故障 : ARRAY[0..15] OF BOOL;
    w报警数 : WORD;
    w首报警 : WORD;
    w首报警对象 : WORD;
    ab上次气缸故障 : ARRAY[0..53] OF BOOL;
    lw气缸在线 : LWORD;
    (* Axis permit bit n <-> PermitCodes[n]; bit 12 (former names) stays 0. *)
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
    ui请求来源 : UINT;
    b自动请求 : BOOL;
    b处理请求 : BOOL;
    w网络应答序列 : WORD;
    w网络应答结果 : WORD;
    w网络应答对象 : WORD;
    w网络上次拒绝 : WORD;
    w内部序列 : WORD;
END_VAR

StopAllRequested := FALSE;
SoftwareEstopRequested := FALSE;
FOR i循环 := 0 TO 15 DO Runtime.aw轴命令[i循环] := 0; END_FOR;
FOR i循环 := 0 TO 53 DO Runtime.aw气缸命令[i循环] := 0; END_FOR;
fb配置(Execute := FALSE, Request := st请求, Store := 全局变量_保持区.Store);
IF NOT b已初始化 THEN Runtime.b待复位 := TRUE; END_IF;

(* Derive wire soft-limit feedback without manufacturing online or standstill. *)
w首报警 := 0;
w首报警对象 := 0;
FOR i循环 := 0 TO 15 DO
    aw限位[i循环] := Runtime.ast轴[i循环].w限位 AND 3;
    IF (全局变量_保持区.Store.aw轴配置[i循环, 14] AND 1) <> 0 THEN
        di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 0]), 16) OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 1]));
        di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 2]), 16) OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 3]));
        IF Runtime.ast轴[i循环].di位置 >= di正限位 THEN aw限位[i循环] := aw限位[i循环] OR 4; END_IF;
        IF Runtime.ast轴[i循环].di位置 <= di负限位 THEN aw限位[i循环] := aw限位[i循环] OR 8; END_IF;
    END_IF;
    Runtime.ast轴[i循环].w限位 := aw限位[i循环];
    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
        IF Runtime.ast轴[i循环].b故障 THEN
            IF NOT ab上次故障[i循环] AND (w报警数 < 65535) THEN w报警数 := w报警数 + 1; END_IF;
            IF w首报警对象 = 0 THEN
                w首报警 := Runtime.ast轴[i循环].w错误码;
                w首报警对象 := 16#0100 OR UINT_TO_WORD(i循环);
            END_IF;
        END_IF;
        ab上次故障[i循环] := Runtime.ast轴[i循环].b故障;
    END_IF;
END_FOR;
FOR i循环 := 0 TO 53 DO
    IF (lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0 THEN
        IF Runtime.ast气缸[i循环].b故障 THEN
            IF NOT ab上次气缸故障[i循环] AND (w报警数 < 65535) THEN w报警数 := w报警数 + 1; END_IF;
            IF w首报警对象 = 0 THEN
                w首报警 := Runtime.ast气缸[i循环].w错误码;
                w首报警对象 := 16#0200 OR UINT_TO_WORD(i循环);
            END_IF;
        END_IF;
        ab上次气缸故障[i循环] := Runtime.ast气缸[i循环].b故障;
    END_IF;
END_FOR;

(* Start/stop pulses are fed once on the following scan. Cancellation outputs
   reach the physical consumer in this scan, including lease expiry. *)
IF Runtime.b硬急停 OR Runtime.b软急停 THEN b停点动脉冲 := TRUE; END_IF;
IF fb看门狗.JogActive THEN
    ui点动索引 := WORD_TO_UINT(fb看门狗.JogObject AND 16#00FF);
    IF NOT Runtime.b手动 OR NOT Runtime.ast轴[ui点动索引].b在线 OR NOT Runtime.ast轴[ui点动索引].b已使能
    OR Runtime.ast轴[ui点动索引].b故障
    OR (Runtime.ast轴[ui点动索引].b正向点动 AND ((aw限位[ui点动索引] AND 5) <> 0))
    OR (Runtime.ast轴[ui点动索引].b负向点动 AND ((aw限位[ui点动索引] AND 10) <> 0)) THEN b停点动脉冲 := TRUE; END_IF;
END_IF;
b签名有效 := (Command[0] = XJV1_SIGNATURE_HI) AND (Command[1] = XJV1_SIGNATURE_LO);
fb看门狗(SignatureOK := b签名有效, Heartbeat := Command[2],
    LeaseCounter := Command[12], LeaseObject := Command[13],
    LeaseSequence := Command[14], StartJog := b起点动脉冲,
    StartObject := w起点动对象, StartSequence := w起点动序列, StopJog := b停点动脉冲);
b起点动脉冲 := FALSE;
b停点动脉冲 := FALSE;
(* A SEQ left in the Holding image by a previous session (or present at power
   up) is never executed: it becomes the baseline on start and on reconnect. *)
IF NOT b已初始化 OR fb看门狗.ConnectedEdge THEN
    w上次序列 := Command[4];
    b已初始化 := TRUE;
END_IF;
IF fb看门狗.CancelJog THEN
    ui点动索引 := WORD_TO_UINT(fb看门狗.JogObject AND 16#00FF);
    Runtime.aw轴命令[ui点动索引] := 26;
END_IF;

(* Reset is stop -> settled scan -> reset pulse -> adapter completion.
   A timeout leaves PendingReset set and never restores a previous action. *)
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
    StopAllRequested := TRUE;
    w上次拒绝 := 17;
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

Runtime.bHMI在线 := fb看门狗.Online;
Runtime.b复位中 := ui复位阶段 <> 0;
FOR ui请求来源 := 0 TO 16 DO
b自动请求 := ui请求来源 <> 0;
b处理请求 := FALSE;
IF NOT b自动请求 THEN
    b处理请求 := (Command[4] <> 0) AND (Command[4] <> w上次序列);
    IF b处理请求 THEN
    st请求 := Command;
    w上次序列 := st请求[4];
    END_IF;
ELSE
    ui轴号 := ui请求来源 - 1;
    b处理请求 := 全局变量_轴请求.ast请求[ui轴号].b忙
        AND NOT 全局变量_轴请求.ast请求[ui轴号].b已下发;
    IF b处理请求 THEN
        w网络应答序列 := w应答序列;
        w网络应答结果 := w应答结果;
        w网络应答对象 := w应答对象;
        w网络上次拒绝 := w上次拒绝;
        FOR i循环 := 0 TO 31 DO st请求[i循环] := 0; END_FOR;
        st请求[0] := XJV1_SIGNATURE_HI;
        st请求[1] := XJV1_SIGNATURE_LO;
        st请求[3] := 全局变量_轴请求.ast请求[ui轴号].w命令;
        (* Never match a stale consumer completion, including WORD wrap. *)
        w内部序列 := Runtime.ast轴[ui轴号].w序列 + 1;
        IF w内部序列 = 0 THEN w内部序列 := 1; END_IF;
        st请求[4] := w内部序列;
        st请求[5] := 16#0100 OR UINT_TO_WORD(ui轴号);
        IF st请求[3] = 29 THEN
            st请求[7] := UINT_TO_WORD(全局变量_轴请求.ast请求[ui轴号].ui槽号);
        END_IF;
    END_IF;
END_IF;
IF b处理请求 THEN
    w应答序列 := st请求[4];
    w应答对象 := st请求[5];
    w应答结果 := 14;
    w校验 := 函数_校验(Request := st请求);
    w类别 := SHR(st请求[5], 8);
    ui轴号 := WORD_TO_UINT(st请求[5] AND 16#00FF);
    IF w校验 <> 0 THEN
        w应答结果 := w校验;
    ELSE
        w应答结果 := 函数_动作许可(Code := st请求[3], ObjectWord := st请求[5],
            HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
            Resetting := ui复位阶段 <> 0, b自动请求 := b自动请求,
            Runtime := Runtime, Store := 全局变量_保持区.Store);
        IF b自动请求 AND StopAllRequested AND (st请求[3] <> 26) THEN w应答结果 := 19; END_IF;
        IF w应答结果 = 0 THEN
            CASE st请求[3] OF
                1:
                    Runtime.b待复位 := TRUE;
                    w复位序列 := st请求[4];
                    ui复位阶段 := 1;
                    StopAllRequested := TRUE;
                    b停点动脉冲 := TRUE;
                2, 3, 4:
                    (* 整机启动/暂停/恢复。受理由 函数_动作许可 决定，
                       这里只把已受理的命令转成一扫描事件交给 PRG 的运行状态机。 *)
                    IF st请求[3] = 2 THEN Runtime.b启动脉冲 := TRUE; END_IF;
                    IF st请求[3] = 3 THEN Runtime.b暂停脉冲 := TRUE; END_IF;
                    IF st请求[3] = 4 THEN Runtime.b恢复脉冲 := TRUE; END_IF;
                9, 10:
                    StopAllRequested := TRUE;
                    b停点动脉冲 := TRUE;
                    ui复位阶段 := 0;
                    IF st请求[3] = 10 THEN
                        Runtime.b软急停 := TRUE;
                        Runtime.b待复位 := TRUE;
                        SoftwareEstopRequested := TRUE;
                    END_IF;
                11: Runtime.b软急停 := FALSE;
                40, 41, 42:
                    (* HMI与中文API共享单槽提交及内部UDINT请求号。 *)
                    IF 气缸_提交(缸号 := ui轴号, 命令 := st请求[3], 自动 := FALSE, Runtime := Runtime) = 0 THEN
                        w应答结果 := 10;
                    ELSE
                        Runtime.aw气缸命令[ui轴号] := st请求[3];
                        Runtime.aw气缸序列[ui轴号] := st请求[4];
                    END_IF;
                31, 50:
                    fb配置(Execute := TRUE, Request := st请求, Store := 全局变量_保持区.Store);
                    w应答结果 := fb配置.Result;
                    IF w应答结果 = 0 THEN Runtime.b待复位 := TRUE; END_IF;
                52:
                    IF st请求[7] <> fb配置.Epoch THEN w应答结果 := 16;
                    ELSE
                        全局变量_保持区.Store.b已确认 := TRUE;
                        Runtime.b待复位 := TRUE;
                        fb配置.Epoch := fb配置.Epoch + 1;
                    END_IF;
                20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30:
                    di目标 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(st请求[6]), 16) OR WORD_TO_DWORD(st请求[7]));
                    udi速度 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(st请求[8]), 16) OR WORD_TO_DWORD(st请求[9]));
                    IF (st请求[3] = 22) OR (st请求[3] = 24) OR (st请求[3] = 25) THEN
                        udi速度 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 4]), 16)
                            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 5]));
                    END_IF;
                    IF st请求[3] = 28 THEN
                        li宽目标 := DINT_TO_LINT(Runtime.ast轴[ui轴号].di位置) + DINT_TO_LINT(di目标);
                        IF (li宽目标 < LINT#-2147483648) OR (li宽目标 > LINT#2147483647) THEN w应答结果 := 28;
                        ELSE di目标 := LINT_TO_DINT(li宽目标);
                        END_IF;
                    ELSIF st请求[3] = 29 THEN
                        i点位索引 := WORD_TO_UINT(st请求[7]);
                        IF (SHR(全局变量_保持区.Store.aw点位[i点位索引, 4], 2) AND WORD#16#000F) <> UINT_TO_WORD(ui轴号)
                        OR ((全局变量_保持区.Store.aw点位[i点位索引, 4] AND 3) <> 3) THEN w应答结果 := 18;
                        ELSE
                            di目标 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 0]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 1]));
                            udi速度 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 2]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 3]));
                        END_IF;
                    END_IF;
                    IF (w应答结果 = 0) AND ((st请求[3] = 22) OR (st请求[3] = 30) OR (st请求[3] = 27)
                        OR (st请求[3] = 28) OR (st请求[3] = 29)) THEN
                        di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 0]), 16)
                            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 1]));
                        di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 2]), 16)
                            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 3]));
                        IF ((全局变量_保持区.Store.aw轴配置[ui轴号, 14] AND 1) <> 0)
                        AND ((di目标 < di负限位) OR (di目标 > di正限位)) THEN w应答结果 := 27;
                        ELSIF ((di目标 > Runtime.ast轴[ui轴号].di位置) AND ((aw限位[ui轴号] AND 5) <> 0))
                        OR ((di目标 < Runtime.ast轴[ui轴号].di位置) AND ((aw限位[ui轴号] AND 10) <> 0)) THEN w应答结果 := 17;
                        END_IF;
                        IF (st请求[3] <> 30) AND ((udi速度 = 0) OR (udi速度 > UDINT#2147483647)) THEN w应答结果 := 28; END_IF;
                    END_IF;
                    IF w应答结果 = 0 THEN
                        IF (st请求[3] = 22) OR (st请求[3] = 24) OR (st请求[3] = 25)
                        OR (st请求[3] = 27) OR (st请求[3] = 28) OR (st请求[3] = 29) THEN
                            IF NOT 函数_额定值(AxisIndex := ui轴号, Field := 2, Value := udi速度) THEN
                                w应答结果 := 22;
                            END_IF;
                        END_IF;
                    END_IF;
                    IF w应答结果 = 0 THEN
                        Runtime.aw轴命令[ui轴号] := st请求[3];
                        Runtime.aw轴序列[ui轴号] := st请求[4];
                        IF (st请求[3] = 27) OR (st请求[3] = 28) OR (st请求[3] = 29) THEN
                            Runtime.aw轴命令[ui轴号] := 27;
                        END_IF;
                        IF (st请求[3] = 22) OR (st请求[3] = 24) OR (st请求[3] = 25)
                        OR (st请求[3] = 27) OR (st请求[3] = 28) OR (st请求[3] = 29) THEN
                            Runtime.adi轴目标[ui轴号] := di目标;
                            Runtime.audi轴速度[ui轴号] := udi速度;
                            Runtime.audi轴加速度[ui轴号] := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 8]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 9]));
                            Runtime.audi轴减速度[ui轴号] := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 10]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 11]));
                            Runtime.audi轴停止减速度[ui轴号] := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 12]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 13]));
                        END_IF;
                        IF (st请求[3] = 24) OR (st请求[3] = 25) THEN
                            b起点动脉冲 := TRUE;
                            w起点动对象 := st请求[5];
                            w起点动序列 := st请求[4];
                        END_IF;
                        IF (st请求[3] = 21) OR (st请求[3] = 26) THEN
                            IF fb看门狗.JogObject = st请求[5] THEN b停点动脉冲 := TRUE; END_IF;
                            ui复位阶段 := 0;
                        END_IF;
                    END_IF;
            ELSE
                w应答结果 := 14;
            END_CASE;
        END_IF;
    END_IF;
    IF b自动请求 THEN
        全局变量_轴请求.ast请求[ui轴号].w序列 := st请求[4];
        全局变量_轴请求.ast请求[ui轴号].w错误 := w应答结果;
        IF w应答结果 = 0 THEN
            全局变量_轴请求.ast请求[ui轴号].b已下发 := TRUE;
            IF st请求[3] = 26 THEN
                全局变量_轴请求.ast请求[ui轴号].w错误 := 19;
            END_IF;
        ELSE
            全局变量_轴请求.ast请求[ui轴号].b忙 := FALSE;
        END_IF;
        (* Internal requests never advance or overwrite the network ACK. *)
        w应答序列 := w网络应答序列;
        w应答结果 := w网络应答结果;
        w应答对象 := w网络应答对象;
        w上次拒绝 := w网络上次拒绝;
    ELSE
        IF w应答结果 <> 0 THEN w上次拒绝 := w应答结果; END_IF;
        w应答纪元 := w应答纪元 + 1;
    END_IF;
END_IF;
END_FOR;
Runtime.b复位中 := ui复位阶段 <> 0;

(* Safety and soft-limit cancellation override any ordinary pulse in this scan. *)
b安全停止 := Runtime.b硬急停 OR Runtime.b软急停;
IF b安全停止 THEN
    b停点动脉冲 := TRUE;
    IF Runtime.b硬急停 THEN Runtime.b待复位 := TRUE; END_IF;
END_IF;
FOR i循环 := 0 TO 15 DO
    IF (w已绑定轴 AND Runtime.w轴消费掩码 AND SHL(WORD#1, i循环)) <> 0 THEN
        IF StopAllRequested OR (b安全停止 AND Runtime.ast轴[i循环].b运动中) OR (Runtime.ast轴[i循环].b运动中 AND
            (((Runtime.ast轴[i循环].di速度 > 0) AND ((aw限位[i循环] AND 5) <> 0))
            OR ((Runtime.ast轴[i循环].di速度 < 0) AND ((aw限位[i循环] AND 10) <> 0)))) THEN
            IF Runtime.aw轴命令[i循环] <> 21 THEN Runtime.aw轴命令[i循环] := 26; END_IF;
        END_IF;
        IF (Runtime.aw轴命令[i循环] = 26) OR (Runtime.aw轴命令[i循环] = 21) THEN
            IF Runtime.audi轴停止减速度[i循环] = 0 THEN
                Runtime.audi轴停止减速度[i循环] := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 12]), 16)
                    OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 13]));
            END_IF;
        END_IF;
    END_IF;
END_FOR;

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
    Published[XJV1_STATUS_BASE + 3] := w应答序列;
    Published[XJV1_STATUS_BASE + 4] := w应答结果;
    Published[XJV1_STATUS_BASE + 5] := w应答对象;
    Published[XJV1_STATUS_BASE + 6] := w应答纪元;
    w系统字 := 0;
    IF fb看门狗.Online THEN w系统字 := w系统字 OR 1; END_IF;
    IF Runtime.b手动 THEN w系统字 := w系统字 OR 2; END_IF;
    IF Runtime.b运行 THEN w系统字 := w系统字 OR 4; END_IF;
    IF ui复位阶段 <> 0 THEN w系统字 := w系统字 OR 8; END_IF;
    IF Runtime.b硬急停 OR Runtime.b软急停 THEN w系统字 := w系统字 OR 16; END_IF;
    IF w首报警对象 <> 0 THEN w系统字 := w系统字 OR 32; END_IF;
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
            AND ab气缸映射已核验[i循环] AND ab气缸模块就绪[i循环] THEN
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
            IF aw限位[i循环] <> 0 THEN w摘要 := w摘要 OR 16; END_IF;
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
                    HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                    Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
                IF w许可结果 = 0 THEN Published[ui基址 + 6] := Published[ui基址 + 6] OR SHL(WORD#1, i子循环); END_IF;
            END_FOR;
            Published[ui基址 + 7] := 函数_动作许可(Code := 27, ObjectWord := 16#0100 OR UINT_TO_WORD(i循环),
                HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
            Published[ui基址 + 8] := Runtime.ast轴[i循环].w错误码;
            Published[ui基址 + 9] := DWORD_TO_WORD(SHR(Runtime.ast轴[i循环].dw驱动错误, 16));
            Published[ui基址 + 10] := DWORD_TO_WORD(Runtime.ast轴[i循环].dw驱动错误);
            Published[ui基址 + 11] := Runtime.ast轴[i循环].w序列;
            Published[ui基址 + 12] := Runtime.ast轴[i循环].w运动结果;
            Published[ui基址 + 13] := aw限位[i循环];
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
                HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 1; END_IF;
            w许可结果 := 函数_动作许可(Code := 41, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 2; END_IF;
            w许可结果 := 函数_动作许可(Code := 50, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
            IF w许可结果 = 0 THEN Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] := Published[ui基址 + XJV1_CYLINDER_LIVE_PERMIT_OFFSET] OR 4; END_IF;
            Published[ui基址 + XJV1_CYLINDER_LIVE_REASON_OFFSET] := 函数_动作许可(Code := 40, ObjectWord := 16#0200 OR UINT_TO_WORD(i循环),
                HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
                Resetting := ui复位阶段 <> 0, Runtime := Runtime, Store := 全局变量_保持区.Store);
            Published[ui基址 + XJV1_CYLINDER_LIVE_ALARM_OFFSET] := Runtime.ast气缸[i循环].w错误码;
        ELSE
            Published[ui基址 + XJV1_CYLINDER_LIVE_REASON_OFFSET] := 4;
        END_IF;
    END_FOR;
    FOR i循环 := 0 TO 119 DO
        ui基址 := XJV1_POINTS_BASE + i循环 * XJV1_POINTS_STRIDE;
        FOR i子循环 := 0 TO 4 DO Published[ui基址 + i子循环] := 全局变量_保持区.Store.aw点位[i循环, i子循环]; END_FOR;
    END_FOR;
    w许可结果 := 函数_动作许可(Code := 1, ObjectWord := 0, HmiOnline := fb看门狗.Online,
        JogBusy := fb看门狗.JogActive OR b起点动脉冲, Resetting := ui复位阶段 <> 0,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_REASON_OFFSET] := w许可结果;
    IF w许可结果 = 0 THEN w全局许可 := w全局许可 OR 16; END_IF;
    w许可结果 := 函数_动作许可(Code := 11, ObjectWord := 0, HmiOnline := fb看门狗.Online,
        JogBusy := fb看门狗.JogActive OR b起点动脉冲, Resetting := ui复位阶段 <> 0,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    IF (w许可结果 = 0) AND Runtime.b软急停 THEN w全局许可 := w全局许可 OR 256; END_IF;
    w许可结果 := 函数_动作许可(Code := 52, ObjectWord := 0, HmiOnline := fb看门狗.Online,
        JogBusy := fb看门狗.JogActive OR b起点动脉冲, Resetting := ui复位阶段 <> 0,
        Runtime := Runtime, Store := 全局变量_保持区.Store);
    IF w许可结果 = 0 THEN w全局许可 := w全局许可 OR 512; END_IF;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_PERMIT_OFFSET] := w全局许可;
    IF w全局许可 <> 0 THEN Published[XJV1_STATUS_BASE + XJV1_STATUS_GLOBAL_REASON_OFFSET] := 0; END_IF;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_FIRST_ALARM_OFFSET] := w首报警;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_FIRST_ALARM_OBJECT_OFFSET] := w首报警对象;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_ALARM_COUNT_OFFSET] := w报警数;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_LAST_REJECTION_OFFSET] := w上次拒绝;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_UPTIME_S_OFFSET] := UDINT_TO_WORD(SHR(udi运行时间, 16));
    Published[XJV1_STATUS_BASE + XJV1_STATUS_UPTIME_S_OFFSET + 1] := UDINT_TO_WORD(udi运行时间);
    Published[XJV1_STATUS_BASE + XJV1_STATUS_BINDING_EPOCH_OFFSET] := w绑定纪元;
    Published[XJV1_STATUS_BASE + XJV1_STATUS_CONFIG_EPOCH_OFFSET] := fb配置.Epoch;
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
