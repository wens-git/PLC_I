(* One serialized control-task owner: Server -> axis consumers.
   Command is the Holding Register image of the official ModbusTCP slave
   (read-only here). A command is committed when Command[4] (SEQ) changes to a
   nonzero value different from the last consumed SEQ; the host writes SEQ last
   with its own FC06 after every payload write succeeded. The whole block is
   copied once on that scan, so later host writes cannot alter it.
   Published is the Input Register image; the owned publisher writes it last.
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
    fb诊断 : 功能块_诊断汇总;
    fb发布 : 功能块_状态发布;
    fb复位 : 功能块_系统复位;
    st通信 : 结构体_通信状态;
    st请求 : 类型_命令区;
    b已初始化 : BOOL;
    w上次序列 : WORD;
    b签名有效 : BOOL;
    b起点动脉冲 : BOOL;
    b停点动脉冲 : BOOL;
    w起点动对象 : WORD;
    w起点动序列 : WORD;
    ui点动索引 : UINT;
    b安全停止 : BOOL;
    ui轴号 : UINT;
    i点位索引 : UINT;
    w校验 : WORD;
    di目标 : DINT;
    li宽目标 : LINT;
    udi速度 : UDINT;
    di正限位 : DINT;
    di负限位 : DINT;
    i循环 : UINT;
    ui请求来源 : UINT;
    b自动请求 : BOOL;
    b处理请求 : BOOL;
    w网络应答序列 : WORD;
    w网络应答结果 : WORD;
    w网络应答对象 : WORD;
    w网络上次拒绝 : WORD;
    w内部序列 : WORD;
END_VAR

(* ===== 区域 1：扫描初始化。清零一扫描命令，保持配置 FB 调用 ===== *)
StopAllRequested := FALSE;
SoftwareEstopRequested := FALSE;
FOR i循环 := 0 TO 15 DO Runtime.aw轴命令[i循环] := 0; END_FOR;
FOR i循环 := 0 TO 53 DO Runtime.aw气缸命令[i循环] := 0; END_FOR;
fb配置(Execute := FALSE, Request := st请求, Store := 全局变量_保持区.Store);
IF NOT b已初始化 THEN Runtime.b待复位 := TRUE; END_IF;

(* ===== 区域 2：限位与报警汇总。只读运行时状态，不产生命令 ===== *)
fb诊断(Runtime := Runtime);

(* Start/stop pulses are fed once on the following scan. Cancellation outputs
   reach the physical consumer in this scan, including lease expiry. *)
IF Runtime.b硬急停 OR Runtime.b软急停 THEN b停点动脉冲 := TRUE; END_IF;
IF fb看门狗.JogActive THEN
    ui点动索引 := WORD_TO_UINT(fb看门狗.JogObject AND 16#00FF);
    IF NOT Runtime.b手动 OR NOT Runtime.ast轴[ui点动索引].b在线 OR NOT Runtime.ast轴[ui点动索引].b已使能
    OR Runtime.ast轴[ui点动索引].b故障
    OR (Runtime.ast轴[ui点动索引].b正向点动 AND ((fb诊断.Summary.aw限位[ui点动索引] AND 5) <> 0))
    OR (Runtime.ast轴[ui点动索引].b负向点动 AND ((fb诊断.Summary.aw限位[ui点动索引] AND 10) <> 0)) THEN b停点动脉冲 := TRUE; END_IF;
END_IF;
b签名有效 := (Command[0] = XJV1_SIGNATURE_HI) AND (Command[1] = XJV1_SIGNATURE_LO);
fb看门狗(SignatureOK := b签名有效, Heartbeat := Command[2],
    LeaseCounter := Command[12], LeaseObject := Command[13],
    LeaseSequence := Command[14], StartJog := b起点动脉冲,
    StartObject := w起点动对象, StartSequence := w起点动序列, StopJog := b停点动脉冲);
b起点动脉冲 := FALSE;
b停点动脉冲 := FALSE;
(* ===== 区域 3：通信看门狗与心跳。判定 HMI 在线、点动租约 ===== *)
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

(* ===== 区域 4：全局复位编排。停止 -> 静止 -> 复位 -> 完成 ===== *)
fb复位(Operation := 0, Sequence := 0, Runtime := Runtime);
IF fb复位.StopRequested THEN StopAllRequested := TRUE; END_IF;
IF fb复位.Failed THEN st通信.w上次拒绝 := 17; END_IF;
Runtime.bHMI在线 := fb看门狗.Online;
Runtime.b复位中 := fb复位.Busy;
(* ===== 区域 5：命令处理。网络命令与内部轴/气缸请求共用校验与许可 ===== *)
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
        w网络应答序列 := st通信.w应答序列;
        w网络应答结果 := st通信.w应答结果;
        w网络应答对象 := st通信.w应答对象;
        w网络上次拒绝 := st通信.w上次拒绝;
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
    st通信.w应答序列 := st请求[4];
    st通信.w应答对象 := st请求[5];
    st通信.w应答结果 := 14;
    w校验 := 函数_校验(Request := st请求);
    ui轴号 := WORD_TO_UINT(st请求[5] AND 16#00FF);
    IF w校验 <> 0 THEN
        st通信.w应答结果 := w校验;
    ELSE
        st通信.w应答结果 := 函数_动作许可(Code := st请求[3], ObjectWord := st请求[5],
            HmiOnline := fb看门狗.Online, JogBusy := fb看门狗.JogActive OR b起点动脉冲,
            Resetting := fb复位.Busy, b自动请求 := b自动请求,
            Runtime := Runtime, Store := 全局变量_保持区.Store);
        IF b自动请求 AND StopAllRequested AND (st请求[3] <> 26) THEN st通信.w应答结果 := 19; END_IF;
        IF st通信.w应答结果 = 0 THEN
            CASE st请求[3] OF
                1:
                    fb复位(Operation := 1, Sequence := st请求[4], Runtime := Runtime);
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
                    fb复位(Operation := 2, Sequence := 0, Runtime := Runtime);
                    IF st请求[3] = 10 THEN
                        Runtime.b软急停 := TRUE;
                        Runtime.b待复位 := TRUE;
                        SoftwareEstopRequested := TRUE;
                    END_IF;
                11: Runtime.b软急停 := FALSE;
                40, 41, 42:
                    (* HMI与中文API共享单槽提交及内部UDINT请求号。 *)
                    IF 气缸_提交(缸号 := ui轴号, 命令 := st请求[3], 自动 := FALSE, Runtime := Runtime) = 0 THEN
                        st通信.w应答结果 := 10;
                    ELSE
                        Runtime.aw气缸命令[ui轴号] := st请求[3];
                        Runtime.aw气缸序列[ui轴号] := st请求[4];
                    END_IF;
                31, 50:
                    fb配置(Execute := TRUE, Request := st请求, Store := 全局变量_保持区.Store);
                    st通信.w应答结果 := fb配置.Result;
                    IF st通信.w应答结果 = 0 THEN Runtime.b待复位 := TRUE; END_IF;
                52:
                    IF st请求[7] <> fb配置.Epoch THEN st通信.w应答结果 := 16;
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
                        IF (li宽目标 < LINT#-2147483648) OR (li宽目标 > LINT#2147483647) THEN st通信.w应答结果 := 28;
                        ELSE di目标 := LINT_TO_DINT(li宽目标);
                        END_IF;
                    ELSIF st请求[3] = 29 THEN
                        i点位索引 := WORD_TO_UINT(st请求[7]);
                        IF (SHR(全局变量_保持区.Store.aw点位[i点位索引, 4], 2) AND WORD#16#000F) <> UINT_TO_WORD(ui轴号)
                        OR ((全局变量_保持区.Store.aw点位[i点位索引, 4] AND 3) <> 3) THEN st通信.w应答结果 := 18;
                        ELSE
                            di目标 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 0]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 1]));
                            udi速度 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 2]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw点位[i点位索引, 3]));
                        END_IF;
                    END_IF;
                    IF (st通信.w应答结果 = 0) AND ((st请求[3] = 22) OR (st请求[3] = 30) OR (st请求[3] = 27)
                        OR (st请求[3] = 28) OR (st请求[3] = 29)) THEN
                        di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 0]), 16)
                            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 1]));
                        di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 2]), 16)
                            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[ui轴号, 3]));
                        IF ((全局变量_保持区.Store.aw轴配置[ui轴号, 14] AND 1) <> 0)
                        AND ((di目标 < di负限位) OR (di目标 > di正限位)) THEN st通信.w应答结果 := 27;
                        ELSIF ((di目标 > Runtime.ast轴[ui轴号].di位置) AND ((fb诊断.Summary.aw限位[ui轴号] AND 5) <> 0))
                        OR ((di目标 < Runtime.ast轴[ui轴号].di位置) AND ((fb诊断.Summary.aw限位[ui轴号] AND 10) <> 0)) THEN st通信.w应答结果 := 17;
                        END_IF;
                        IF (st请求[3] <> 30) AND ((udi速度 = 0) OR (udi速度 > UDINT#2147483647)) THEN st通信.w应答结果 := 28; END_IF;
                    END_IF;
                    IF st通信.w应答结果 = 0 THEN
                        IF (st请求[3] = 22) OR (st请求[3] = 24) OR (st请求[3] = 25)
                        OR (st请求[3] = 27) OR (st请求[3] = 28) OR (st请求[3] = 29) THEN
                            IF NOT 函数_额定值(AxisIndex := ui轴号, Field := 2, Value := udi速度) THEN
                                st通信.w应答结果 := 22;
                            END_IF;
                        END_IF;
                    END_IF;
                    IF st通信.w应答结果 = 0 THEN
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
                            fb复位(Operation := 2, Sequence := 0, Runtime := Runtime);
                        END_IF;
                    END_IF;
            ELSE
                st通信.w应答结果 := 14;
            END_CASE;
        END_IF;
    END_IF;
    IF b自动请求 THEN
        全局变量_轴请求.ast请求[ui轴号].w序列 := st请求[4];
        全局变量_轴请求.ast请求[ui轴号].w错误 := st通信.w应答结果;
        IF st通信.w应答结果 = 0 THEN
            全局变量_轴请求.ast请求[ui轴号].b已下发 := TRUE;
            IF st请求[3] = 26 THEN
                全局变量_轴请求.ast请求[ui轴号].w错误 := 19;
            END_IF;
        ELSE
            全局变量_轴请求.ast请求[ui轴号].b忙 := FALSE;
        END_IF;
        (* Internal requests never advance or overwrite the network ACK. *)
        st通信.w应答序列 := w网络应答序列;
        st通信.w应答结果 := w网络应答结果;
        st通信.w应答对象 := w网络应答对象;
        st通信.w上次拒绝 := w网络上次拒绝;
    ELSE
        IF st通信.w应答结果 <> 0 THEN st通信.w上次拒绝 := st通信.w应答结果; END_IF;
        st通信.w应答纪元 := st通信.w应答纪元 + 1;
    END_IF;
END_IF;
END_FOR;
Runtime.b复位中 := fb复位.Busy;

(* Safety and soft-limit cancellation override any ordinary pulse in this scan. *)
b安全停止 := Runtime.b硬急停 OR Runtime.b软急停;
IF b安全停止 THEN
    b停点动脉冲 := TRUE;
    IF Runtime.b硬急停 THEN Runtime.b待复位 := TRUE; END_IF;
END_IF;
FOR i循环 := 0 TO 15 DO
    IF (w已绑定轴 AND Runtime.w轴消费掩码 AND SHL(WORD#1, i循环)) <> 0 THEN
        IF StopAllRequested OR (b安全停止 AND Runtime.ast轴[i循环].b运动中) OR (Runtime.ast轴[i循环].b运动中 AND
            (((Runtime.ast轴[i循环].di速度 > 0) AND ((fb诊断.Summary.aw限位[i循环] AND 5) <> 0))
            OR ((Runtime.ast轴[i循环].di速度 < 0) AND ((fb诊断.Summary.aw限位[i循环] AND 10) <> 0)))) THEN
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

(* ===== 区域 6：定时器与状态发布。仅写发布区，不驱动设备 ===== *)
st通信.bHMI在线 := fb看门狗.Online;
st通信.b点动忙 := fb看门狗.JogActive OR b起点动脉冲;
st通信.w配置纪元 := fb配置.Epoch;
fb发布(Communication := st通信, Diagnostics := fb诊断.Summary,
    Runtime := Runtime, Published := Published);
END_FUNCTION_BLOCK
