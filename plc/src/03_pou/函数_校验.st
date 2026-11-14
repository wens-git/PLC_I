(* Validates request envelope only; unsupported payload semantics never apply. *)
FUNCTION 函数_校验 : WORD
VAR_INPUT
    Request : 类型_命令区;
END_VAR
VAR
    w类别 : WORD;
    i索引 : WORD;
    w命令码 : WORD;
    dw参数A : DWORD;
    dw参数B : DWORD;
    dw参数C : DWORD;
    (* Local loop index: never bind to the legacy global i. *)
    i循环 : INT;
END_VAR

函数_校验 := 0;
IF (Request[0] <> XJV1_SIGNATURE_HI) OR (Request[1] <> XJV1_SIGNATURE_LO) THEN
    函数_校验 := 1; RETURN;
END_IF;
w命令码 := Request[3];
w类别 := SHR(Request[5], 8);
i索引 := Request[5] AND 16#00FF;
IF (w类别 > 3) OR ((w类别 = 0) AND (i索引 <> 0))
OR ((w类别 = 1) AND (i索引 >= 16))
OR ((w类别 = 2) AND (i索引 >= 54))
OR ((w类别 = 3) AND (i索引 >= 120)) THEN
    函数_校验 := 15; RETURN;
END_IF;
CASE w命令码 OF
    1, 2, 3, 4, 9, 10, 11, 52, 53:
        IF w类别 <> 0 THEN 函数_校验 := 15; RETURN; END_IF;
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31:
        IF w类别 <> 1 THEN 函数_校验 := 15; RETURN; END_IF;
    40, 41, 42:
        IF w类别 <> 2 THEN 函数_校验 := 15; RETURN; END_IF;
    50:
        IF w类别 = 0 THEN 函数_校验 := 15; RETURN; END_IF;
ELSE
    函数_校验 := 14; RETURN;
END_CASE;
IF Request[15] <> 0 THEN 函数_校验 := 9; RETURN; END_IF;
IF w命令码 <> 50 THEN
    FOR i循环 := 16 TO 31 DO
        IF Request[i循环] <> 0 THEN 函数_校验 := 9; RETURN; END_IF;
    END_FOR;
END_IF;
dw参数A := SHL(WORD_TO_DWORD(Request[6]), 16) OR WORD_TO_DWORD(Request[7]);
dw参数B := SHL(WORD_TO_DWORD(Request[8]), 16) OR WORD_TO_DWORD(Request[9]);
dw参数C := SHL(WORD_TO_DWORD(Request[10]), 16) OR WORD_TO_DWORD(Request[11]);
CASE w命令码 OF
    27, 28:
        IF (dw参数B = 0) OR (dw参数B > 2147483647) OR (dw参数C <> 0) THEN
            函数_校验 := 9;
        END_IF;
    29:
        IF (dw参数A >= 120) OR (dw参数B <> 0) OR (dw参数C <> 0) THEN 函数_校验 := 9; END_IF;
    31:
        IF (dw参数A >= 120) OR (dw参数C = 0) OR (dw参数C > 2147483647) THEN 函数_校验 := 9; END_IF;
    50:
        IF (dw参数A = 0) OR (dw参数B > 65535) OR (dw参数C <> 0)
        OR ((w类别 = 1) AND (dw参数A > 255))
        OR ((w类别 <> 1) AND (dw参数A > 7)) THEN 函数_校验 := 9; END_IF;
    52:
        IF (dw参数A > 65535) OR (dw参数B <> 0) OR (dw参数C <> 0) THEN 函数_校验 := 9; END_IF;
    53:
        IF (dw参数A <> 16#A55A) OR (dw参数B <> 0) OR (dw参数C <> 0) THEN 函数_校验 := 9; END_IF;
ELSE
    IF (dw参数A <> 0) OR (dw参数B <> 0) OR (dw参数C <> 0) THEN 函数_校验 := 9; END_IF;
END_CASE;
END_FUNCTION
