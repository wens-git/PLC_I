(* Run after physical consumers. Track only requests submitted by the axis API. *)
FUNCTION_BLOCK 功能块_轴请求监视
VAR_IN_OUT
    Runtime : 结构体_运行时;
END_VAR
VAR
    i循环 : UINT;
    atmr接收 : ARRAY[0..15] OF TON;
    b取消 : BOOL;
END_VAR

FOR i循环 := 0 TO 15 DO
    atmr接收[i循环](IN := 全局变量_轴请求.ast请求[i循环].b忙
        AND 全局变量_轴请求.ast请求[i循环].b已下发
        AND NOT 全局变量_轴请求.ast请求[i循环].b已接收, PT := T#1s);
    IF 全局变量_轴请求.ast请求[i循环].b忙
    AND 全局变量_轴请求.ast请求[i循环].b已下发 THEN
        b取消 := Runtime.b硬急停 OR Runtime.b软急停
            OR NOT Runtime.bHMI在线 OR Runtime.b复位中 OR Runtime.b待复位
            OR NOT Runtime.b运行 OR Runtime.b暂停
            OR (Runtime.aw轴命令[i循环] = 21) OR (Runtime.aw轴命令[i循环] = 26);
        IF 全局变量_轴请求.ast请求[i循环].w命令 = 26 THEN
            (* Stop completion is never motion Done. Wait for physical settling. *)
            IF Runtime.ast轴[i循环].b静止 AND NOT Runtime.ast轴[i循环].b运动中 THEN
                全局变量_轴请求.ast请求[i循环].b忙 := FALSE;
            END_IF;
        ELSIF b取消 THEN
            全局变量_轴请求.ast请求[i循环].b忙 := FALSE;
            全局变量_轴请求.ast请求[i循环].w错误 := 19;
        ELSIF Runtime.ast轴[i循环].b故障 OR NOT Runtime.ast轴[i循环].b在线 THEN
            全局变量_轴请求.ast请求[i循环].b忙 := FALSE;
            全局变量_轴请求.ast请求[i循环].w错误 := 17;
        ELSIF Runtime.ast轴[i循环].w序列 = 全局变量_轴请求.ast请求[i循环].w序列 THEN
            全局变量_轴请求.ast请求[i循环].b已接收 := TRUE;
            IF (Runtime.ast轴[i循环].w运动结果 = 2)
            AND Runtime.ast轴[i循环].b静止 AND NOT Runtime.ast轴[i循环].b运动中 THEN
                全局变量_轴请求.ast请求[i循环].b完成 := TRUE;
                全局变量_轴请求.ast请求[i循环].b忙 := FALSE;
            ELSIF (Runtime.ast轴[i循环].w运动结果 = 3)
            OR (Runtime.ast轴[i循环].w运动结果 = 4) THEN
                全局变量_轴请求.ast请求[i循环].b忙 := FALSE;
                全局变量_轴请求.ast请求[i循环].w错误 := 17;
            END_IF;
        ELSIF 全局变量_轴请求.ast请求[i循环].b已接收 OR atmr接收[i循环].Q THEN
            (* Delivery is uncertain: queue a real stop for the next Server scan. *)
            全局变量_轴请求.ast请求[i循环].w命令 := 26;
            全局变量_轴请求.ast请求[i循环].b已下发 := FALSE;
            全局变量_轴请求.ast请求[i循环].b已接收 := FALSE;
            全局变量_轴请求.ast请求[i循环].w错误 := 19;
        END_IF;
    END_IF;
END_FOR;
END_FUNCTION_BLOCK
