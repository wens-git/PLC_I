(* Isolated simulator test task only. Never schedule with real machine control.
   Cold/reset-origin starts a fresh run; Done latches until the next reset.
   Watch 程序_自测.Passed/Failed/Done/FirstFailure.
   Protocol 1.2: Modbus is the official slave device, so the former Access
   adapter cases are gone; requests are fed to 功能块_配置 directly.
   Expected terminal result: Done=TRUE, Passed=61, Failed=0, FirstFailure=0.
   FirstFailure is the 1-based case ID (Step + 1); one case per active scan,
   separated by an idle scan to release Execute and Request.
   No network, device references, retained GVL, external assertion or library.
*)
PROGRAM 程序_自测
VAR
    udi通过 : UDINT;
    udi失败 : UDINT;
    b完成 : BOOL;
    ui首失败 : UINT;
    ui首失败步骤 : UINT;
    w首失败结果 : WORD;
    w首失败对象 : WORD;
    ui步骤 : UINT;
    b空闲扫描 : BOOL;
    fb配置 : 功能块_配置;
    st配置 : 结构体_配置;
    st原配置 : 结构体_配置;
    st请求 : 类型_命令区;
    w原纪元 : WORD;
    w原结果 : WORD;
    w期望纪元 : WORD;
    w期望结果 : WORD;
    b执行配置 : BOOL;
    b检查回滚 : BOOL;
    b检查空闲 : BOOL;
    b正常 : BOOL;
    i点位索引 : INT;
    i循环 : INT;
    i子循环 : INT;
END_VAR

IF b完成 THEN RETURN; END_IF;
IF b空闲扫描 THEN
    fb配置(Execute := FALSE, Request := st请求, Store := st配置);
    b空闲扫描 := FALSE;
    RETURN;
END_IF;

FOR i循环 := 0 TO 31 DO st请求[i循环] := 0; END_FOR;
st请求[0] := WORD#16#584A;
st请求[1] := XJV1_SIGNATURE_LO;
st请求[4] := 1;
st请求[5] := WORD#16#0100;
b执行配置 := FALSE;
b检查回滚 := FALSE;
b检查空闲 := FALSE;
w期望结果 := 0;
b正常 := TRUE;

CASE ui步骤 OF
    0:
        st配置.dw签名 := 0;
        st配置.b已确认 := TRUE;
    1:
        (* Wrong signature is rejected before any record changes. *)
        st请求[1] := WORD#16#5631; st请求[3] := 31; st请求[7] := 19; st请求[11] := 1;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 1;
    2:
        (* Non-zero reserved header word +15. *)
        st请求[3] := 31; st请求[7] := 19; st请求[11] := 1; st请求[15] := 1;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    3:
        (* Command 51 (retired PLC name commit) is unsupported. *)
        st请求[3] := 51; st请求[5] := WORD#16#0100;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 14;
    4:
        (* Code 50 on the system object is an illegal object. *)
        st请求[3] := 50; st请求[5] := 0; st请求[7] := 1;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 15;
    5:
        (* Point index 120 is out of the pool. *)
        st请求[3] := 50; st请求[5] := WORD#16#0378; st请求[7] := 4;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 15;
    6:
        (* Free slots are exactly XJV1_POINT_FREE after cold init. *)
        b检查空闲 := TRUE; b检查回滚 := TRUE;
        b正常 := (st配置.aw点位[19, 4] = XJV1_POINT_FREE) AND (fb配置.Epoch = 0);
    7:
        (* Free bit combined with an owner is never accepted. *)
        st请求[3] := 50; st请求[5] := WORD#16#0313; st请求[7] := 4; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[19, i循环]; END_FOR;
        st请求[20] := XJV1_POINT_FREE OR WORD#16#0004;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    8:
        (* Release of P0 standby slot 0 (owned by axis 0) is rejected. *)
        st请求[3] := 50; st请求[5] := WORD#16#0300; st请求[7] := 4; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[0, i循环]; END_FOR;
        st请求[20] := XJV1_POINT_FREE;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    9:
        (* Stale config epoch. *)
        st请求[3] := 50; st请求[5] := WORD#16#0313; st请求[7] := 4; st请求[9] := fb配置.Epoch + 1;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[19, i循环]; END_FOR;
        st请求[20] := WORD#16#0000;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 16;
    10:
        (* Teach claims free slot 19 for axis 0: position -1000, speed 65536. *)
        st请求[3] := 31; st请求[7] := 19;
        st请求[8] := WORD#16#FFFF; st请求[9] := WORD#16#FC18;
        st请求[10] := 1; st请求[11] := 0;
        b执行配置 := TRUE;
    11:
        st请求[3] := 31; st请求[7] := 19; st请求[11] := 1; st请求[15] := 1;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    12..31:
        i点位索引 := UINT_TO_INT(ui步骤) - 12;
        (* Deliberate fixture: alternating disabled/enabled already-taught points. *)
        IF (i点位索引 MOD 2) = 0 THEN st配置.aw点位[i点位索引, 4] := 0;
        ELSE st配置.aw点位[i点位索引, 4] := 3; END_IF;
        st配置.b已确认 := TRUE;
        st请求[3] := 31;
        st请求[7] := INT_TO_WORD(i点位索引);
        st请求[8] := WORD#16#FFFF;
        st请求[9] := DINT_TO_WORD(DINT#64536 - INT_TO_DINT(i点位索引));
        st请求[10] := 1; st请求[11] := INT_TO_WORD(i点位索引);
        b执行配置 := TRUE;
    32..37:
        st请求[3] := 50;
        st请求[7] := 4;
        st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 15 DO st请求[16 + i循环] := st配置.aw轴配置[0, i循环]; END_FOR;
        b执行配置 := TRUE;
        CASE ui步骤 OF
            32:
                st配置.b已确认 := TRUE;
                st请求[16] := 0; st请求[17] := 0;
                st请求[20] := 1; st请求[21] := 2;
            33:
                st请求[20] := 0; st请求[21] := 0;
                b检查回滚 := TRUE; w期望结果 := 22;
            34:
                st请求[7] := 1;
                st请求[16] := st配置.aw轴配置[0, 2]; st请求[17] := st配置.aw轴配置[0, 3];
                b检查回滚 := TRUE; w期望结果 := 21;
            35:
                st请求[9] := 0;
                b检查回滚 := TRUE; w期望结果 := 16;
            36:
                st请求[8] := 1;
                b检查回滚 := TRUE; w期望结果 := 9;
            37:
                st请求[31] := 1;
                b检查回滚 := TRUE; w期望结果 := 9;
        END_CASE;
    38:
        st请求[3] := 50; st请求[5] := WORD#16#0314;
        st请求[7] := 4; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[20, i循环]; END_FOR;
        st请求[20] := 3;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    39:
        st配置.aw点位[19, 4] := 2;
        st配置.b已确认 := TRUE;
        st请求[3] := 50; st请求[5] := WORD#16#0313;
        st请求[7] := 4; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[19, i循环]; END_FOR;
        st请求[20] := 3;
        b执行配置 := TRUE;
    40:
        st请求[3] := 31; st请求[7] := 19;
        st请求[8] := WORD#16#8000; st请求[9] := 0;
        st请求[10] := WORD#16#7FFF; st请求[11] := WORD#16#FFFF;
        b执行配置 := TRUE;
    41..50:
        (* Retired name commit 51 must stay unsupported for every object kind. *)
        st请求[3] := 51;
        CASE ui步骤 OF
            41, 42, 43: st请求[5] := WORD#16#0100;
            44, 45, 46: st请求[5] := WORD#16#0200;
        ELSE st请求[5] := WORD#16#0300;
        END_CASE;
        st请求[7] := fb配置.Epoch; st请求[16] := 65;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 14;
    51..53:
        st请求[3] := 31; st请求[7] := 19; st请求[11] := 1;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
        CASE ui步骤 OF
            51: st请求[6] := 1;
            52: st请求[7] := 120;
            53: st请求[10] := WORD#16#8000; st请求[11] := 0;
        END_CASE;
    54:
        b检查空闲 := TRUE; b检查回滚 := TRUE;
    55:
        (* Cylinder 1 is unbound in production binding: parameter commit rejects 4. *)
        st请求[3] := 50; st请求[5] := WORD#16#0201; st请求[7] := 1; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 7 DO st请求[16 + i循环] := st配置.aw气缸配置[1, i循环]; END_FOR;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 4;
    56:
        (* Axis 15 owner bits (16#003C) and the free code are distinct. Slot 15's
           cold-init owner is verified in step 0; slots 0..19 are re-owned by the
           step 12..31 fixture, so check an untouched free slot here. *)
        b检查空闲 := TRUE; b检查回滚 := TRUE;
        b正常 := (st配置.aw点位[20, 4] = XJV1_POINT_FREE) AND (XJV1_POINT_FREE <> SHL(WORD#15, 2));
    57:
        (* Point index 160 is out of range. *)
        st请求[3] := 50; st请求[5] := WORD#16#03A0; st请求[7] := 4;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 15;
    58:
        st请求[3] := 50; st请求[5] := WORD#16#0313;
        st请求[7] := 2; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[19, i循环]; END_FOR;
        st请求[18] := WORD#16#8000; st请求[19] := 0;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    59:
        (* Release slot 19: disable + untaught is required; taught slot rejects 9. *)
        st请求[3] := 50; st请求[5] := WORD#16#0313; st请求[7] := 4; st请求[9] := fb配置.Epoch;
        FOR i循环 := 0 TO 4 DO st请求[16 + i循环] := st配置.aw点位[19, i循环]; END_FOR;
        st请求[20] := XJV1_POINT_FREE;
        b执行配置 := TRUE; b检查回滚 := TRUE; w期望结果 := 9;
    60:
        st请求[3] := 31; st请求[7] := 19; st请求[11] := 999;
        b检查空闲 := TRUE; b检查回滚 := TRUE;
ELSE
    b正常 := FALSE;
END_CASE;

st原配置 := st配置;
w原纪元 := fb配置.Epoch;
w原结果 := fb配置.Result;
fb配置(Execute := b执行配置, Request := st请求, Store := st配置);
IF b执行配置 THEN
    IF fb配置.Result <> w期望结果 THEN b正常 := FALSE; END_IF;
    w期望纪元 := w原纪元;
    IF w期望结果 = 0 THEN
        IF w原纪元 = WORD#16#FFFF THEN w期望纪元 := 0;
        ELSE w期望纪元 := w原纪元 + 1; END_IF;
    END_IF;
    IF fb配置.Epoch <> w期望纪元 THEN b正常 := FALSE; END_IF;
END_IF;
IF b检查空闲 AND (fb配置.Result <> w原结果) THEN b正常 := FALSE; END_IF;

IF b检查回滚 THEN
    IF (fb配置.Epoch <> w原纪元) OR (st配置.dw签名 <> st原配置.dw签名)
    OR (st配置.b已确认 <> st原配置.b已确认) THEN b正常 := FALSE; END_IF;
    FOR i循环 := 0 TO 15 DO
        FOR i子循环 := 0 TO 15 DO
            IF st配置.aw轴配置[i循环, i子循环] <> st原配置.aw轴配置[i循环, i子循环] THEN b正常 := FALSE; END_IF;
        END_FOR;
    END_FOR;
    FOR i循环 := 0 TO 53 DO
        FOR i子循环 := 0 TO 7 DO
            IF st配置.aw气缸配置[i循环, i子循环] <> st原配置.aw气缸配置[i循环, i子循环] THEN b正常 := FALSE; END_IF;
        END_FOR;
    END_FOR;
    FOR i循环 := 0 TO 119 DO
        FOR i子循环 := 0 TO 4 DO
            IF st配置.aw点位[i循环, i子循环] <> st原配置.aw点位[i循环, i子循环] THEN b正常 := FALSE; END_IF;
        END_FOR;
    END_FOR;
END_IF;

CASE ui步骤 OF
    0:
        b正常 := (st配置.dw签名 = XJV1_SIGNATURE) AND NOT st配置.b已确认 AND (fb配置.Epoch = 0);
        FOR i循环 := 0 TO 119 DO
            IF i循环 < 16 THEN
                IF st配置.aw点位[i循环, 4] <> SHL(INT_TO_WORD(i循环), 2) THEN b正常 := FALSE; END_IF;
            ELSIF st配置.aw点位[i循环, 4] <> XJV1_POINT_FREE THEN b正常 := FALSE; END_IF;
            IF st配置.aw点位[i循环, 3] <> 1 THEN b正常 := FALSE; END_IF;
        END_FOR;
        FOR i循环 := 0 TO 53 DO
            FOR i子循环 := 1 TO 4 DO
                IF st配置.aw气缸配置[i循环, i子循环] <> WORD#16#FFFF THEN b正常 := FALSE; END_IF;
            END_FOR;
            IF (st配置.aw气缸配置[i循环, 5] <> 200) OR (st配置.aw气缸配置[i循环, 6] <> 3000) THEN b正常 := FALSE; END_IF;
        END_FOR;
    10:
        IF (st配置.aw点位[19, 0] <> WORD#16#FFFF) OR (st配置.aw点位[19, 1] <> WORD#16#FC18)
        OR (st配置.aw点位[19, 2] <> 1) OR (st配置.aw点位[19, 3] <> 0)
        OR (st配置.aw点位[19, 4] <> 2) OR st配置.b已确认 THEN b正常 := FALSE; END_IF;
    12..31:
        IF (st配置.aw点位[i点位索引, 0] <> WORD#16#FFFF)
        OR (st配置.aw点位[i点位索引, 1] <> DINT_TO_WORD(DINT#64536 - INT_TO_DINT(i点位索引)))
        OR (st配置.aw点位[i点位索引, 2] <> 1) OR (st配置.aw点位[i点位索引, 3] <> INT_TO_WORD(i点位索引))
        OR (st配置.aw点位[i点位索引, 4] <> (st原配置.aw点位[i点位索引, 4] OR WORD#16#0002))
        OR st配置.b已确认 THEN b正常 := FALSE; END_IF;
    32:
        FOR i子循环 := 0 TO 15 DO
            IF i子循环 = 4 THEN
                IF st配置.aw轴配置[0, i子循环] <> 1 THEN b正常 := FALSE; END_IF;
            ELSIF i子循环 = 5 THEN
                IF st配置.aw轴配置[0, i子循环] <> 2 THEN b正常 := FALSE; END_IF;
            ELSIF st配置.aw轴配置[0, i子循环] <> st原配置.aw轴配置[0, i子循环] THEN b正常 := FALSE;
            END_IF;
        END_FOR;
        IF st配置.b已确认 THEN b正常 := FALSE; END_IF;
    39:
        IF (st配置.aw点位[19, 4] <> 3) OR st配置.b已确认 THEN b正常 := FALSE; END_IF;
        FOR i子循环 := 0 TO 3 DO
            IF st配置.aw点位[19, i子循环] <> st原配置.aw点位[19, i子循环] THEN b正常 := FALSE; END_IF;
        END_FOR;
    40:
        IF (st配置.aw点位[19, 0] <> WORD#16#8000) OR (st配置.aw点位[19, 1] <> 0)
        OR (st配置.aw点位[19, 2] <> WORD#16#7FFF) OR (st配置.aw点位[19, 3] <> WORD#16#FFFF)
        OR (st配置.aw点位[19, 4] <> 3) THEN b正常 := FALSE; END_IF;
END_CASE;

IF b正常 THEN
    udi通过 := udi通过 + 1;
ELSE
    udi失败 := udi失败 + 1;
    IF ui首失败 = 0 THEN ui首失败 := ui步骤 + 1; END_IF;
    IF ui首失败 = ui步骤 + 1 THEN
        ui首失败步骤 := ui步骤;
        w首失败结果 := fb配置.Result;
        w首失败对象 := st请求[5];
    END_IF;
END_IF;
IF ui步骤 >= 60 THEN
    b完成 := TRUE;
ELSE
    ui步骤 := ui步骤 + 1;
    b空闲扫描 := TRUE;
END_IF;
END_PROGRAM
