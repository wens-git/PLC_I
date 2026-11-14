(* Call every control scan with the same retained Store. Execute is a one-scan
   pulse from the server AFTER its sole action-permission decision. Request is
   the server's immutable committed copy; this FB does not consume SEQ or ACK.
   Execute=FALSE still initializes an invalid signature and preserves Result.
   Result is synchronous: 0 committed, otherwise protocol rejection; failure
   leaves records, confirmation and Epoch untouched (except cold initialization).
   Epoch is volatile and starts at zero. Server-owned command 52 must compare
   against this Epoch, then increment it modulo 65536 after successful confirmation.
   Server also owns the power-up pending-reset latch and binding-change handling.
   Parameter and taught-point commits clear Confirmed. Display names are
   host-owned since protocol 1.2; this FB never stores text.
   Publication and this FB must run serially in the same task. The commit loops
   are scan-atomic to that consumer, not a claim of power-loss atomicity.
   Engineering ratings must be commissioned; zero rejects parameter commits.
   Engineering binding currently has zero cylinders; future wiring integration
   must populate their read-only Store fields from verified engineering constants.
   Point pool: flags bit0 enable, bit1 taught, bit2..5 owner axis 0..15,
   bit7..15 zero. A free slot is exactly XJV1_POINT_FREE (bit6 only), so axis 15
   (owner bits = 15) never collides with "free". Internally Owner = 16 means free.
   Free slots are claimed by code 50 or by teach (31); release (-> XJV1_POINT_FREE)
   requires the point to be disabled and clears its taught record. P0 of axis i
   is slot i and is never released. *)
FUNCTION_BLOCK 功能块_配置
VAR_INPUT
    Execute : BOOL;
    Request : 类型_命令区;
    (* Server advances this for command 52; omit from ordinary FB calls.
       No call site may pass Epoch explicitly: it would overwrite the
       server-side epoch advance shared through this instance member. *)
    Epoch : WORD;
END_VAR
VAR_OUTPUT
    Result : WORD;
END_VAR
VAR_IN_OUT
    Store : 结构体_配置;
END_VAR
VAR
    w命令码 : WORD;
    w类别 : WORD;
    i索引 : INT;
    i轴号 : INT;
    i归属 : INT;
    i新归属 : INT;
    i点位索引 : INT;
    w掩码 : WORD;
    aw候选 : ARRAY[0..15] OF WORD;
    dw值 : DWORD;
    di位置 : DINT;
    di正限位 : DINT;
    di负限位 : DINT;
    i循环 : INT;
    i子循环 : INT;
END_VAR

(* 1.2到1.3布局不变：只迁移旧flags为动点延时，保留全部轴/点位。 *)
IF Store.dw签名 = DWORD#16#584A5632 THEN
    FOR i循环 := 0 TO 53 DO
        Store.aw气缸配置[i循环, 7] := Store.aw气缸配置[i循环, 5];
    END_FOR;
    Store.b已确认 := FALSE;
    Store.dw签名 := XJV1_SIGNATURE;
END_IF;
IF Store.dw签名 <> XJV1_SIGNATURE THEN
    FOR i循环 := 0 TO 15 DO
        FOR i子循环 := 0 TO 15 DO Store.aw轴配置[i循环, i子循环] := 0; END_FOR;
        (* Full DINT range, soft limits enabled; all point enables remain off. *)
        Store.aw轴配置[i循环, 0] := WORD#16#7FFF;
        Store.aw轴配置[i循环, 1] := WORD#16#FFFF;
        Store.aw轴配置[i循环, 2] := WORD#16#8000;
        FOR i子循环 := 2 TO 6 DO Store.aw轴配置[i循环, i子循环 * 2 + 1] := 1; END_FOR;
        Store.aw轴配置[i循环, 14] := 1;
    END_FOR;
    FOR i循环 := 0 TO 53 DO
        FOR i子循环 := 0 TO 7 DO Store.aw气缸配置[i循环, i子循环] := 0; END_FOR;
        FOR i子循环 := 1 TO 4 DO Store.aw气缸配置[i循环, i子循环] := WORD#16#FFFF; END_FOR;
        Store.aw气缸配置[i循环, 5] := 200;
        Store.aw气缸配置[i循环, 6] := 3000;
        Store.aw气缸配置[i循环, 7] := 200;
    END_FOR;
    (* Slots 0..15 pre-own to their like-numbered axis as P0; the rest are free. *)
    FOR i循环 := 0 TO 119 DO
        FOR i子循环 := 0 TO 4 DO Store.aw点位[i循环, i子循环] := 0; END_FOR;
        Store.aw点位[i循环, 3] := 1;
        IF i循环 < 16 THEN
            Store.aw点位[i循环, 4] := SHL(INT_TO_WORD(i循环), 2);
        ELSE
            Store.aw点位[i循环, 4] := XJV1_POINT_FREE;
        END_IF;
    END_FOR;
    Store.b已确认 := FALSE;
    (* Signature last: partial cold initialization must not look valid. *)
    Store.dw签名 := XJV1_SIGNATURE;
END_IF;
(* 工程表每扫描覆盖前5字，绝不保留旧flags高位或猜测物理映射。 *)
FOR i循环 := 0 TO 53 DO
    IF (Store.aw气缸配置[i循环, 0] <> 全局变量_气缸工程.aw类型[i循环])
        OR (Store.aw气缸配置[i循环, 1] <> 全局变量_气缸工程.aw动点输出[i循环])
        OR (Store.aw气缸配置[i循环, 2] <> 全局变量_气缸工程.aw原点输出[i循环])
        OR (Store.aw气缸配置[i循环, 3] <> 全局变量_气缸工程.aw动点输入[i循环])
        OR (Store.aw气缸配置[i循环, 4] <> 全局变量_气缸工程.aw原点输入[i循环]) THEN
        Store.b已确认 := FALSE;
    END_IF;
    Store.aw气缸配置[i循环, 0] := 全局变量_气缸工程.aw类型[i循环];
    Store.aw气缸配置[i循环, 1] := 全局变量_气缸工程.aw动点输出[i循环];
    Store.aw气缸配置[i循环, 2] := 全局变量_气缸工程.aw原点输出[i循环];
    Store.aw气缸配置[i循环, 3] := 全局变量_气缸工程.aw动点输入[i循环];
    Store.aw气缸配置[i循环, 4] := 全局变量_气缸工程.aw原点输入[i循环];
END_FOR;
IF NOT Execute THEN RETURN; END_IF;

Result := 函数_校验(Request := Request);
IF Result <> 0 THEN RETURN; END_IF;
w命令码 := Request[3];
IF (w命令码 <> 31) AND (w命令码 <> 50) THEN
    Result := 14; RETURN;
END_IF;
w类别 := SHR(Request[5], 8);
i索引 := WORD_TO_INT(Request[5] AND WORD#16#00FF);
i轴号 := i索引;
i归属 := -1;
IF w类别 = 2 THEN
    IF (全局变量_绑定.lw已绑定气缸 AND SHL(LWORD#1, i索引)) = 0 THEN
        Result := 4; RETURN;
    END_IF;
ELSE
    IF w类别 = 3 THEN
        IF Store.aw点位[i索引, 4] = XJV1_POINT_FREE THEN
            i归属 := 16;
        ELSE
            i归属 := WORD_TO_INT(SHR(Store.aw点位[i索引, 4], 2) AND WORD#16#000F);
            i轴号 := i归属;
        END_IF;
        IF i归属 = 16 THEN
            (* Free slot: only a code-50 claim passes here, mirroring permit. *)
            IF w命令码 <> 50 THEN Result := 4; RETURN; END_IF;
        ELSE
            IF (全局变量_绑定.w已绑定轴 AND SHL(WORD#1, i轴号)) = 0 THEN
                Result := 4; RETURN;
            END_IF;
        END_IF;
    ELSE
        IF (全局变量_绑定.w已绑定轴 AND SHL(WORD#1, i轴号)) = 0 THEN
            Result := 4; RETURN;
        END_IF;
    END_IF;
END_IF;
IF (w命令码 = 50) AND (Request[9] <> Epoch) THEN Result := 16; RETURN; END_IF;

w掩码 := Request[7];
IF (w命令码 = 50) AND (w类别 = 1) THEN
    FOR i子循环 := 0 TO 15 DO aw候选[i子循环] := Store.aw轴配置[i索引, i子循环]; END_FOR;
    IF (Request[30] AND WORD#16#FFFE) <> 0 THEN Result := 9; RETURN; END_IF;
    IF Request[31] <> 0 THEN Result := 9; RETURN; END_IF;
    FOR i循环 := 0 TO 6 DO
        IF (w掩码 AND SHL(WORD#1, i循环)) <> 0 THEN
            aw候选[i循环 * 2] := Request[16 + i循环 * 2];
            aw候选[i循环 * 2 + 1] := Request[17 + i循环 * 2];
        END_IF;
    END_FOR;
    IF (w掩码 AND WORD#16#0080) <> 0 THEN aw候选[14] := Request[30]; END_IF;
    di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(aw候选[0]), 16) OR WORD_TO_DWORD(aw候选[1]));
    di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(aw候选[2]), 16) OR WORD_TO_DWORD(aw候选[3]));
    IF di负限位 >= di正限位 THEN Result := 21; RETURN; END_IF;
    FOR i循环 := 2 TO 6 DO
        dw值 := SHL(WORD_TO_DWORD(aw候选[i循环 * 2]), 16) OR WORD_TO_DWORD(aw候选[i循环 * 2 + 1]);
        IF (dw值 = 0) OR (dw值 > DWORD#2147483647) THEN Result := 函数_参数码(INT_TO_UINT(i循环)); RETURN; END_IF;
        IF NOT 函数_额定值(AxisIndex := INT_TO_UINT(i轴号), Field := INT_TO_UINT(i循环),
            Value := DWORD_TO_UDINT(dw值)) THEN Result := 函数_参数码(INT_TO_UINT(i循环)); RETURN; END_IF;
    END_FOR;
    IF ((aw候选[14] AND WORD#16#FFFE) <> 0) OR (aw候选[15] <> 0) THEN
        Result := 20; RETURN;
    END_IF;
ELSIF (w命令码 = 50) AND (w类别 = 2) THEN
    FOR i子循环 := 0 TO 7 DO aw候选[i子循环] := Store.aw气缸配置[i索引, i子循环]; END_FOR;
    FOR i子循环 := 0 TO 4 DO
        IF Request[16 + i子循环] <> Store.aw气缸配置[i索引, i子循环] THEN Result := 9; RETURN; END_IF;
    END_FOR;
    FOR i子循环 := 24 TO 31 DO
        IF Request[i子循环] <> 0 THEN Result := 9; RETURN; END_IF;
    END_FOR;
    IF (w掩码 AND WORD#16#0001) <> 0 THEN aw候选[5] := Request[21]; END_IF;
    IF (w掩码 AND WORD#16#0002) <> 0 THEN aw候选[6] := Request[22]; END_IF;
    IF (w掩码 AND WORD#16#0004) <> 0 THEN aw候选[7] := Request[23]; END_IF;
    IF (aw候选[0] AND WORD#16#FFF0) <> 0 THEN Result := 9; RETURN; END_IF;
    IF aw候选[1] = WORD#16#FFFF THEN Result := 9; RETURN; END_IF;
    IF ((aw候选[0] AND 3) = 0) OR ((aw候选[0] AND 3) = 2) THEN
        IF aw候选[2] <> WORD#16#FFFF THEN Result := 9; RETURN; END_IF;
    ELSE
        IF (aw候选[2] = WORD#16#FFFF) OR (aw候选[1] = aw候选[2]) THEN Result := 9; RETURN; END_IF;
    END_IF;
    FOR i子循环 := 1 TO 4 DO
        IF (aw候选[i子循环] <> WORD#16#FFFF) AND (aw候选[i子循环] >= 128) THEN
            Result := 9; RETURN;
        END_IF;
    END_FOR;
    IF (aw候选[6] = 0) OR (aw候选[5] >= aw候选[6]) OR (aw候选[7] >= aw候选[6])
        OR ((aw候选[3] = WORD#16#FFFF) AND (aw候选[5] = 0))
        OR ((aw候选[4] = WORD#16#FFFF) AND (aw候选[7] = 0)) THEN
        Result := 9; RETURN;
    END_IF;
ELSE
    (* Kind 3 point pool records; command 31 arrives as kind 1 (object axis). *)
    IF w命令码 = 31 THEN
        i点位索引 := WORD_TO_INT(Request[7] AND WORD#16#00FF);
        IF Store.aw点位[i点位索引, 4] = XJV1_POINT_FREE THEN
            i归属 := 16;
        ELSE
            i归属 := WORD_TO_INT(SHR(Store.aw点位[i点位索引, 4], 2) AND WORD#16#000F);
        END_IF;
        IF (i归属 <> i轴号) AND (i归属 <> 16) THEN Result := 18; RETURN; END_IF;
    ELSE
        i点位索引 := i索引;
    END_IF;
    FOR i子循环 := 0 TO 4 DO aw候选[i子循环] := Store.aw点位[i点位索引, i子循环]; END_FOR;
    IF w命令码 = 31 THEN
        aw候选[0] := Request[8];
        aw候选[1] := Request[9];
        aw候选[2] := Request[10];
        aw候选[3] := Request[11];
        (* Teaching keeps the enable bit, sets taught and (re)asserts the owner;
           a claimed free slot drops the free bit. *)
        aw候选[4] := SHL(INT_TO_WORD(i轴号), 2) OR WORD#16#0002;
        IF i归属 <> 16 THEN
            aw候选[4] := aw候选[4] OR (Store.aw点位[i点位索引, 4] AND WORD#16#0001);
        END_IF;
        i新归属 := i轴号;
    ELSE
        FOR i子循环 := 21 TO 31 DO
            IF Request[i子循环] <> 0 THEN Result := 9; RETURN; END_IF;
        END_FOR;
        IF (Request[20] AND NOT XJV1_POINT_VALID_MASK) <> 0 THEN Result := 9; RETURN; END_IF;
        IF ((Request[20] AND XJV1_POINT_FREE) <> 0) AND (Request[20] <> XJV1_POINT_FREE) THEN
            Result := 9; RETURN;
        END_IF;
        (* Only teaching (31) sets taught; a release to XJV1_POINT_FREE is the one
           code-50 write allowed to clear it, so it is exempt from this check. *)
        IF ((Request[20] AND WORD#16#0002) <> (Store.aw点位[i点位索引, 4] AND WORD#16#0002))
        AND (Request[20] <> XJV1_POINT_FREE) THEN
            Result := 9; RETURN;
        END_IF;
        IF (w掩码 AND WORD#16#0001) <> 0 THEN
            aw候选[0] := Request[16]; aw候选[1] := Request[17];
        END_IF;
        IF (w掩码 AND WORD#16#0002) <> 0 THEN
            aw候选[2] := Request[18]; aw候选[3] := Request[19];
        END_IF;
        IF (w掩码 AND WORD#16#0004) <> 0 THEN aw候选[4] := Request[20]; END_IF;
        IF aw候选[4] = XJV1_POINT_FREE THEN
            i新归属 := 16;
        ELSE
            i新归属 := WORD_TO_INT(SHR(aw候选[4], 2) AND WORD#16#000F);
        END_IF;
        IF i归属 = 16 THEN
            IF i新归属 = 16 THEN Result := 9; RETURN; END_IF;
            IF (全局变量_绑定.w已绑定轴 AND SHL(WORD#1, i新归属)) = 0 THEN
                Result := 4; RETURN;
            END_IF;
        ELSE
            IF (i新归属 <> i归属) AND (i新归属 <> 16) THEN Result := 9; RETURN; END_IF;
            (* Release requires a disabled point. Writing XJV1_POINT_FREE also
               clears the taught record, so a released slot can never be reclaimed
               and enabled without being taught again. *)
            IF (i新归属 = 16) AND ((Store.aw点位[i点位索引, 4] AND WORD#16#0001) <> 0) THEN
                Result := 9; RETURN;
            END_IF;
            (* Slot i is the P0 standby point of axis i and is never released. *)
            IF (i新归属 = 16) AND (i点位索引 = i归属) THEN Result := 9; RETURN; END_IF;
        END_IF;
    END_IF;
    IF ((aw候选[4] AND NOT XJV1_POINT_VALID_MASK) <> 0)
    OR (((aw候选[4] AND XJV1_POINT_FREE) <> 0) AND (aw候选[4] <> XJV1_POINT_FREE))
    OR ((aw候选[4] AND WORD#16#0003) = WORD#16#0001) THEN Result := 9; RETURN; END_IF;
    IF i新归属 <> 16 THEN
        dw值 := SHL(WORD_TO_DWORD(aw候选[2]), 16) OR WORD_TO_DWORD(aw候选[3]);
        IF (dw值 = 0) OR (dw值 > DWORD#2147483647) THEN Result := 9; RETURN; END_IF;
        IF NOT 函数_额定值(AxisIndex := INT_TO_UINT(i新归属), Field := 2,
            Value := DWORD_TO_UDINT(dw值)) THEN Result := 9; RETURN; END_IF;
        di位置 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(aw候选[0]), 16) OR WORD_TO_DWORD(aw候选[1]));
        IF (Store.aw轴配置[i新归属, 14] AND WORD#16#0001) <> 0 THEN
            di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(Store.aw轴配置[i新归属, 0]), 16) OR WORD_TO_DWORD(Store.aw轴配置[i新归属, 1]));
            di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(Store.aw轴配置[i新归属, 2]), 16) OR WORD_TO_DWORD(Store.aw轴配置[i新归属, 3]));
            IF (di位置 < di负限位) OR (di位置 > di正限位) THEN Result := 26; RETURN; END_IF;
        END_IF;
    END_IF;
END_IF;

(* All rejection paths precede this commit boundary. *)
IF (w命令码 = 50) AND (w类别 = 1) THEN
    FOR i子循环 := 0 TO 15 DO Store.aw轴配置[i索引, i子循环] := aw候选[i子循环]; END_FOR;
ELSIF (w命令码 = 50) AND (w类别 = 2) THEN
    FOR i子循环 := 0 TO 7 DO Store.aw气缸配置[i索引, i子循环] := aw候选[i子循环]; END_FOR;
ELSE
    FOR i子循环 := 0 TO 4 DO Store.aw点位[i点位索引, i子循环] := aw候选[i子循环]; END_FOR;
END_IF;
Store.b已确认 := FALSE;
IF Epoch = WORD#16#FFFF THEN
    Epoch := 0;
ELSE
    Epoch := Epoch + 1;
END_IF;
Result := 0;
END_FUNCTION_BLOCK
