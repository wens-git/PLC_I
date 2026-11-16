(* Owns fault-edge history and saturating alarm count. Runtime is a live
   reference; only derived w限位 feedback is written, never device commands. *)
FUNCTION_BLOCK 功能块_诊断汇总
VAR_IN_OUT
    Runtime : 结构体_运行时;
END_VAR
VAR_OUTPUT
    Summary : 结构体_诊断摘要;
END_VAR
VAR
    ab上次故障 : ARRAY[0..15] OF BOOL;
    ab上次气缸故障 : ARRAY[0..53] OF BOOL;
    di正限位 : DINT;
    di负限位 : DINT;
    i循环 : UINT;
END_VAR

(* Derive wire soft-limit feedback without manufacturing online or standstill. *)
Summary.w首报警 := 0;
Summary.w首报警对象 := 0;
FOR i循环 := 0 TO 15 DO
    Summary.aw限位[i循环] := Runtime.ast轴[i循环].w限位 AND 3;
    IF (全局变量_保持区.Store.aw轴配置[i循环, 14] AND 1) <> 0 THEN
        di正限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 0]), 16) OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 1]));
        di负限位 := DWORD_TO_DINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 2]), 16) OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 3]));
        IF Runtime.ast轴[i循环].di位置 >= di正限位 THEN Summary.aw限位[i循环] := Summary.aw限位[i循环] OR 4; END_IF;
        IF Runtime.ast轴[i循环].di位置 <= di负限位 THEN Summary.aw限位[i循环] := Summary.aw限位[i循环] OR 8; END_IF;
    END_IF;
    Runtime.ast轴[i循环].w限位 := Summary.aw限位[i循环];
    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
        IF Runtime.ast轴[i循环].b故障 THEN
            IF NOT ab上次故障[i循环] AND (Summary.w报警数 < 65535) THEN Summary.w报警数 := Summary.w报警数 + 1; END_IF;
            IF Summary.w首报警对象 = 0 THEN
                Summary.w首报警 := Runtime.ast轴[i循环].w错误码;
                Summary.w首报警对象 := 16#0100 OR UINT_TO_WORD(i循环);
            END_IF;
        END_IF;
        ab上次故障[i循环] := Runtime.ast轴[i循环].b故障;
    END_IF;
END_FOR;
FOR i循环 := 0 TO 53 DO
    IF (lw已绑定气缸 AND SHL(LWORD#1, i循环)) <> 0 THEN
        IF Runtime.ast气缸[i循环].b故障 THEN
            IF NOT ab上次气缸故障[i循环] AND (Summary.w报警数 < 65535) THEN Summary.w报警数 := Summary.w报警数 + 1; END_IF;
            IF Summary.w首报警对象 = 0 THEN
                Summary.w首报警 := Runtime.ast气缸[i循环].w错误码;
                Summary.w首报警对象 := 16#0200 OR UINT_TO_WORD(i循环);
            END_IF;
        END_IF;
        ab上次气缸故障[i循环] := Runtime.ast气缸[i循环].b故障;
    END_IF;
END_FOR;
END_FUNCTION_BLOCK
