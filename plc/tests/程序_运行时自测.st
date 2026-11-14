(* Isolated simulator test. Fake feedback, no MC calls or physical outputs.
   Requires the xs_selftest isolated copy: lw已绑定气缸 is patched to 1,
   so cylinder 0 is bound and cylinder 1 stays unbound for these phases; the
   rated arrays are patched to 2147483647, which phase 25 depends on.
   Protocol 1.2: the official ModbusTCP slave writes the Holding image; this test
   writes the same Command array directly (payload first, SEQ last). *)
PROGRAM 程序_运行时自测
VAR
    st命令 : 类型_命令区;
    fb服务端 : 功能块_服务端;
    st发布 : 类型_发布区;
    st运行时 : 结构体_运行时;
    fb看门狗 : 功能块_看门狗;
    ui阶段 : UINT;
    i循环 : UINT;
    b正常 : BOOL;
    b检查 : BOOL;
    b提交 : BOOL;
    w命令码 : WORD;
    w对象字 : WORD;
    w序列 : WORD;
    w标记 : WORD;
    w结果 : WORD;
    udi通过 : UDINT;
    udi失败 : UDINT;
    ui首失败 : UINT;
    b完成 : BOOL;
END_VAR

IF b完成 THEN RETURN; END_IF;
b检查 := FALSE;
b提交 := FALSE;
b正常 := TRUE;
CASE ui阶段 OF
    0:
        全局变量_保持区.Store.dw签名 := 0;
        st运行时.b手动 := TRUE;
        st运行时.w轴消费掩码 := 7;
        FOR i循环 := 0 TO 2 DO
            st运行时.ast轴[i循环].b在线 := TRUE;
            st运行时.ast轴[i循环].b静止 := TRUE;
            st运行时.ast轴[i循环].b可下发 := TRUE;
        END_FOR;
        st命令[0] := XJV1_SIGNATURE_HI;
        st命令[1] := XJV1_SIGNATURE_LO;
    1:
        st命令[2] := 1;
    2:
        w命令码 := 20; w对象字 := 16#0100; b提交 := TRUE;
    3:
        b检查 := TRUE; b正常 := st运行时.aw轴命令[0] = 20;
    4:
        st运行时.ast轴[0].b已使能 := TRUE;
        st运行时.ast轴[0].b运动中 := TRUE;
        st运行时.ast轴[0].b静止 := FALSE;
        w命令码 := 21; b提交 := TRUE;
    5:
        b检查 := TRUE; b正常 := st运行时.aw轴命令[0] = 21;
    6:
        st运行时.ast轴[0].b运动中 := FALSE;
        st运行时.ast轴[0].b静止 := TRUE;
        w命令码 := 10; w对象字 := 0; b提交 := TRUE;
    7:
        b检查 := TRUE; b正常 := st运行时.b软急停 AND (st运行时.aw轴命令[0] = 26);
    8:
        w命令码 := 11; b提交 := TRUE;
    9:
        b检查 := TRUE; b正常 := NOT st运行时.b软急停 AND st运行时.b待复位;
    10:
        st运行时.ast轴[0].b故障 := TRUE;
        st运行时.ast轴[0].b静止 := FALSE;
        st运行时.ast轴[0].di速度 := 0;
        w命令码 := 1; b提交 := TRUE;
    11:
        b检查 := TRUE; b正常 := st运行时.b待复位 AND (st运行时.aw轴命令[0] = 26);
    12: ;
    13:
        b检查 := TRUE; b正常 := (st运行时.aw轴命令[0] = 23) AND (st运行时.aw轴序列[0] = w序列);
        FOR i循环 := 0 TO 2 DO
            st运行时.ast轴[i循环].b故障 := FALSE;
            st运行时.ast轴[i循环].b静止 := TRUE;
            st运行时.ast轴[i循环].w序列 := w序列;
            st运行时.ast轴[i循环].w运动结果 := 2;
        END_FOR;
    14:
        b检查 := TRUE; b正常 := NOT st运行时.b待复位;
    15:
        st运行时.aw轴命令[0] := 26;
        w结果 := 函数_动作许可(Code := 24, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 10;
    16:
        w结果 := 函数_动作许可(Code := 26, ObjectWord := 16#0100,
            HmiOnline := FALSE, JogBusy := TRUE, Resetting := TRUE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 0;
    17:
        w结果 := 函数_动作许可(Code := 2, ObjectWord := 0,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE;
        IF 全局变量_运行配置.b正式流程已接入 THEN b正常 := w结果 = 0;
        ELSE b正常 := w结果 = 12;
        END_IF;
    18:
        st运行时.b硬急停 := TRUE;
        w结果 := 函数_动作许可(Code := 20, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 3;
    19:
        st运行时.b硬急停 := FALSE;
        全局变量_保持区.Store.aw轴配置[0, 0] := 0;
        全局变量_保持区.Store.aw轴配置[0, 1] := 2000;
        全局变量_保持区.Store.aw轴配置[0, 2] := 0;
        全局变量_保持区.Store.aw轴配置[0, 3] := 1000;
        全局变量_保持区.Store.aw轴配置[0, 14] := 1;
        st运行时.ast轴[0].di位置 := 1500;
        w命令码 := 30; w对象字 := 16#0100; b提交 := TRUE;
    20:
        b检查 := TRUE; b正常 := st运行时.aw轴命令[0] = 0;
    21:
        st运行时.ast轴[0].b已使能 := FALSE;
        w结果 := 函数_动作许可(Code := 30, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 6;
    22:
        (* 清故障在报警态必须可重试：残留的运动标志不再拒绝 23。 *)
        st运行时.ast轴[0].b运动中 := TRUE;
        w结果 := 函数_动作许可(Code := 23, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 0;
    23:
        st运行时.ast轴[0].b运动中 := FALSE;
        st运行时.ast轴[0].b可下发 := FALSE;
        w结果 := 函数_动作许可(Code := 20, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 10;
    24:
        st运行时.b硬急停 := TRUE;
        w结果 := 函数_动作许可(Code := 23, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 3;
    25:
        st运行时.b硬急停 := FALSE;
        b检查 := TRUE;
        b正常 := NOT 函数_额定值(AxisIndex := 0, Field := 2, Value := 0)
            AND 函数_额定值(AxisIndex := 0, Field := 2, Value := 2147483647)
            AND NOT 函数_额定值(AxisIndex := 0, Field := 2, Value := 2147483648);
    26:
        b检查 := TRUE;
        b正常 := NOT 函数_额定值(AxisIndex := 16, Field := 2, Value := 1)
            AND NOT 函数_额定值(AxisIndex := 0, Field := 7, Value := 1);
    27:
        w命令码 := 42; w对象字 := 16#0201; b提交 := TRUE;
    28:
        b检查 := TRUE; b正常 := st运行时.aw气缸命令[1] = 0;
    29:
        w命令码 := 42; w对象字 := 16#0200; b提交 := TRUE;
    30:
        b检查 := TRUE; b正常 := (st运行时.aw气缸命令[0] = 42) AND (st运行时.aw气缸序列[0] = w序列);
    31:
        w命令码 := 40; w对象字 := 16#0200; b提交 := TRUE;
    32:
        b检查 := TRUE; b正常 := st运行时.aw气缸命令[0] = 0;
    33:
        w结果 := 函数_动作许可(Code := 42, ObjectWord := 16#0200,
            HmiOnline := FALSE, JogBusy := TRUE, Resetting := TRUE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 0;
    34:
        w结果 := 函数_动作许可(Code := 42, ObjectWord := 16#0201,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 4;
    35:
        fb看门狗(SignatureOK := TRUE, Heartbeat := 6);
    36:
        fb看门狗(SignatureOK := TRUE, Heartbeat := 7);
        b检查 := TRUE; b正常 := fb看门狗.Online;
    37:
        fb看门狗(SignatureOK := TRUE, Heartbeat := 7, StartJog := TRUE,
            StartObject := 16#0100, StartSequence := 9);
        b检查 := TRUE; b正常 := fb看门狗.JogActive;
    38:
        fb看门狗(SignatureOK := TRUE, Heartbeat := 7, StopJog := TRUE);
        b检查 := TRUE; b正常 := fb看门狗.CancelJog AND NOT fb看门狗.JogActive;
    39:
        (* Regression: a start pulse arriving while offline must establish and
           cancel the lease in the same scan instead of being dropped. *)
        fb看门狗(SignatureOK := FALSE, Heartbeat := 7, StartJog := TRUE,
            StartObject := 16#0100, StartSequence := 9);
        b检查 := TRUE; b正常 := fb看门狗.CancelJog AND NOT fb看门狗.JogActive;
    40:
        (* Drop the signature for one scan so the Server's own watchdogs go offline. *)
        w标记 := st运行时.aw轴序列[0];
        st命令[0] := 0;
    41:
        (* A command left in the Holding image across a reconnect is never
           replayed: on the connection edge the Server adopts its SEQ as the
           baseline. Code 26 is used because a stop bypasses every ordinary gate,
           so it would run here if the SEQ were treated as unconsumed. *)
        st命令[0] := XJV1_SIGNATURE_HI;
        w序列 := w序列 + 1;
        st命令[3] := 26;
        st命令[4] := w序列;
        st命令[5] := 16#0100;
    42:
        b检查 := TRUE; b正常 := st运行时.aw轴序列[0] = w标记;
    43:
        (* Positive control: the same payload under a genuinely new SEQ does run,
           so phase 42 can only pass because the SEQ was absorbed, not ignored. *)
        w命令码 := 26; w对象字 := 16#0100; b提交 := TRUE;
    44:
        b检查 := TRUE; b正常 := st运行时.aw轴序列[0] = w序列;
    45:
        st运行时.b硬急停 := FALSE;
        st运行时.b软急停 := TRUE;
        st运行时.b运行 := FALSE;
        st运行时.b待复位 := TRUE;
        w命令码 := 11; w对象字 := 0; b提交 := TRUE;
    46:
        b检查 := TRUE;
        b正常 := NOT st运行时.b软急停 AND NOT st运行时.b运行
            AND st运行时.b待复位;
    47:
        (* Clearing the software latch never restores motion permission:
           the axis is still not cleared for dispatch. *)
        w结果 := 函数_动作许可(Code := 20, ObjectWord := 16#0100,
            HmiOnline := TRUE, JogBusy := FALSE, Resetting := FALSE,
            Runtime := st运行时, Store := 全局变量_保持区.Store);
        b检查 := TRUE; b正常 := w结果 = 10;
    48:
        st运行时.b硬急停 := TRUE;
        st运行时.b软急停 := TRUE;
        w命令码 := 11; w对象字 := 0; b提交 := TRUE;
    49:
        b检查 := TRUE; b正常 := st运行时.b软急停 AND NOT st运行时.b运行;
    50:
        b完成 := TRUE;
END_CASE;
IF b检查 THEN
    IF b正常 THEN udi通过 := udi通过 + 1;
    ELSE
        udi失败 := udi失败 + 1;
        IF ui首失败 = 0 THEN ui首失败 := ui阶段; END_IF;
    END_IF;
END_IF;
IF b提交 THEN
    (* Same order as the host: payload words, then code, then SEQ last. *)
    FOR i循环 := 5 TO 31 DO st命令[i循环] := 0; END_FOR;
    st命令[5] := w对象字;
    st命令[3] := w命令码;
    w序列 := w序列 + 1;
    st命令[4] := w序列;
END_IF;
(* Heartbeat keeps the HMI online for the duration of the test. *)
st命令[2] := st命令[2] + 1;
fb服务端(Command := st命令, Published := st发布, Runtime := st运行时);
ui阶段 := ui阶段 + 1;
END_PROGRAM
