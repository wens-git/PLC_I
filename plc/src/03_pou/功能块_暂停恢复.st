(* 暂停快照与恢复。移植自原程序“暂停快照 / 暂停回位”三段，只保留必要行为：

   暂停沿 -> 对运动中轴下受控停止 26 -> 全部静止后抓拍位置
   恢复请求 -> 对偏离超过容差的轴下发绝对定位 27 回快照位置 -> 结果 2 即完成
   急停 / 轴离线或故障 -> 立即判失败并撤销本块下发的命令

   不产生动作许可，不替代 功能块_轴 的安全判定。
   必须在 功能块_服务端 之后、各轴消费之前调用（服务端每扫描开头清零命令数组）。 *)
FUNCTION_BLOCK 功能块_暂停恢复
VAR_INPUT
    b暂停 : BOOL;
    b请求 : BOOL;
    b急停 : BOOL;
    di容差 : DINT;
    (* 停稳确认时间。原程序为 300 ms；做成输入便于自测用更短的值，
       现场调用保持 300 ms。 *)
    di停稳ms : DINT;
END_VAR
VAR_IN_OUT
    Runtime : 结构体_运行时;
END_VAR
VAR_OUTPUT
    b恢复中 : BOOL;
    b恢复完成 : BOOL;
    b恢复失败 : BOOL;
    b曾偏离 : BOOL;
    b已抓拍 : BOOL;
    (* 内部阶段只读发布，供上位机诊断与自测观察。 *)
    ui内部阶段 : UINT;
END_VAR
VAR
    i阶段 : UINT; (* 0 空闲，1 停车等待静止，2 已抓拍待恢复，3 回位中 *)
    b暂停上周期 : BOOL;
    b请求上周期 : BOOL;
    b请求沿 : BOOL;
    adi快照 : ARRAY[0..15] OF DINT;
    (* 只有收到本轮回位 27 的轴才参与完成判定；未偏离的轴不动作，
       不能被当成“未到位”而把恢复永久卡住。 *)
    ab已下发 : ARRAY[0..15] OF BOOL;
    w序列 : WORD;
    b暂停沿 : BOOL;
    b封锁 : BOOL;
    b全部静止 : BOOL;
    b全部到位 : BOOL;
    tmr停稳 : TON;
    tmr恢复 : TON;
    i循环 : UINT;
END_VAR

b恢复中 := FALSE;
(* b已抓拍 是锁存状态，不是脉冲：暂停沿/解除时清零，抓拍成功时置位。
   上位机与自测都靠它判断“快照是否有效”，脉冲化会漏读。 *)
b暂停沿 := b暂停 AND NOT b暂停上周期;
b暂停上周期 := b暂停;
b请求沿 := b请求 AND NOT b请求上周期;
b请求上周期 := b请求;

(* 安全条件不满足时任何恢复都不成立。 *)
b封锁 := b急停 OR Runtime.b硬急停 OR Runtime.b软急停;
FOR i循环 := 0 TO 15 DO
    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
        b封锁 := b封锁 OR NOT Runtime.ast轴[i循环].b在线 OR Runtime.ast轴[i循环].b故障;
    END_IF;
END_FOR;

IF b暂停沿 THEN
    i阶段 := 1;
    b曾偏离 := FALSE;
    b恢复完成 := FALSE;
    b恢复失败 := FALSE;
    b已抓拍 := FALSE;
    w序列 := w序列 + 1;
    tmr停稳(IN := FALSE, PT := DINT_TO_TIME(di停稳ms));
    FOR i循环 := 0 TO 15 DO
        adi快照[i循环] := Runtime.ast轴[i循环].di位置;
        ab已下发[i循环] := FALSE;
    END_FOR;
ELSIF NOT b暂停 THEN
    i阶段 := 0;
    b曾偏离 := FALSE;
    b已抓拍 := FALSE;
END_IF;

CASE i阶段 OF
    1:
        (* 受控停止。序列固定，重复下发同一序列不会在轴内重复触发。 *)
        b全部静止 := TRUE;
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                IF Runtime.ast轴[i循环].b运动中 OR NOT Runtime.ast轴[i循环].b静止 THEN
                    b全部静止 := FALSE;
                    Runtime.aw轴命令[i循环] := 26;
                    Runtime.aw轴序列[i循环] := w序列;
                END_IF;
            END_IF;
        END_FOR;
        tmr停稳(IN := b全部静止 AND NOT b封锁, PT := DINT_TO_TIME(di停稳ms));
        IF tmr停稳.Q THEN
            (* 停稳后重新抓拍：减速距离不算偏离。 *)
            FOR i循环 := 0 TO 15 DO adi快照[i循环] := Runtime.ast轴[i循环].di位置; END_FOR;
            b已抓拍 := TRUE;
            i阶段 := 2;
        END_IF;
    2:
        (* 暂停期间只监视偏离，不自动动作。 *)
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                IF (Runtime.ast轴[i循环].di位置 - adi快照[i循环]) > di容差
                OR (adi快照[i循环] - Runtime.ast轴[i循环].di位置) > di容差 THEN
                    b曾偏离 := TRUE;
                END_IF;
            END_IF;
        END_FOR;
        (* 恢复请求只在上升沿处理一次：b请求 是电平，重复处理会每扫描
           重新下发 27，命令槽无法释放，安全封锁时也撤不干净。 *)
        IF b请求沿 AND NOT b封锁 THEN
            IF b曾偏离 THEN
                w序列 := w序列 + 1;
                FOR i循环 := 0 TO 15 DO ab已下发[i循环] := FALSE; END_FOR;
                FOR i循环 := 0 TO 15 DO
                    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN
                        IF (Runtime.ast轴[i循环].di位置 - adi快照[i循环]) > di容差
                        OR (adi快照[i循环] - Runtime.ast轴[i循环].di位置) > di容差 THEN
                            (* 回位参数取保持配置，与命令 27 的下发参数同源。 *)
                            Runtime.adi轴目标[i循环] := adi快照[i循环];
                            Runtime.audi轴速度[i循环] := DWORD_TO_UDINT(
                                SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 4]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 5]));
                            Runtime.audi轴加速度[i循环] := DWORD_TO_UDINT(
                                SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 8]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 9]));
                            Runtime.audi轴减速度[i循环] := DWORD_TO_UDINT(
                                SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 10]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 11]));
                            Runtime.audi轴停止减速度[i循环] := DWORD_TO_UDINT(
                                SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 12]), 16)
                                OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 13]));
                            Runtime.aw轴命令[i循环] := 27;
                            Runtime.aw轴序列[i循环] := w序列;
                            ab已下发[i循环] := TRUE;
                        END_IF;
                    END_IF;
                END_FOR;
                tmr恢复(IN := FALSE, PT := T#120s);
                i阶段 := 3;
            ELSE
                (* 没偏离就没有要回的位置，恢复直接成立。 *)
                b恢复完成 := TRUE;
            END_IF;
        END_IF;

    3:
        b恢复中 := TRUE;
        b全部到位 := TRUE;
        FOR i循环 := 0 TO 15 DO
            IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 AND ab已下发[i循环] THEN
                b全部到位 := b全部到位 AND (Runtime.ast轴[i循环].w序列 = w序列)
                    AND (Runtime.ast轴[i循环].w运动结果 = 2)
                    AND Runtime.ast轴[i循环].b静止;
            END_IF;
        END_FOR;
        tmr恢复(IN := TRUE, PT := T#120s);
        IF b封锁 OR tmr恢复.Q THEN
            b恢复失败 := TRUE;
            b恢复中 := FALSE;
            i阶段 := 2;
        ELSIF b全部到位 THEN
            b恢复完成 := TRUE;
            b恢复中 := FALSE;
            i阶段 := 2;
        END_IF;
END_CASE;
ui内部阶段 := i阶段;

(* 封锁时撤销本块下发的 26/27，避免安全状态下留下未消费动作。 *)
IF b封锁 THEN
    FOR i循环 := 0 TO 15 DO
        IF (Runtime.aw轴序列[i循环] = w序列)
        AND ((Runtime.aw轴命令[i循环] = 26) OR (Runtime.aw轴命令[i循环] = 27)) THEN
            Runtime.aw轴命令[i循环] := 0;
        END_IF;
    END_FOR;
    b恢复中 := FALSE;
    IF i阶段 = 3 THEN
        b恢复失败 := TRUE;
        i阶段 := 2;
    END_IF;
END_IF;
END_FUNCTION_BLOCK
