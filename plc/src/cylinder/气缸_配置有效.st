FUNCTION 气缸_配置有效 : BOOL
VAR_INPUT 缸号 : UINT; END_VAR
VAR_IN_OUT Store : 结构体_配置; END_VAR
VAR i : UINT; j : UINT; k : UINT; w类型 : WORD; END_VAR
气缸_配置有效 := FALSE;
IF 缸号 >= 54 THEN RETURN; END_IF;
IF (Store.aw气缸配置[缸号, 0] AND WORD#16#FFF0) <> 0 THEN RETURN; END_IF;
w类型 := Store.aw气缸配置[缸号, 0] AND 3;
(* 输出地址按输出映像容量校验，输入地址按输入映像容量校验。 *)
FOR i := 1 TO 2 DO
    IF (Store.aw气缸配置[缸号, i] <> WORD#16#FFFF) AND (WORD_TO_UINT(Store.aw气缸配置[缸号, i]) >= ui气缸输出点数) THEN RETURN; END_IF;
END_FOR;
FOR i := 3 TO 4 DO
    IF (Store.aw气缸配置[缸号, i] <> WORD#16#FFFF) AND (WORD_TO_UINT(Store.aw气缸配置[缸号, i]) >= ui气缸输入点数) THEN RETURN; END_IF;
END_FOR;
IF Store.aw气缸配置[缸号, 1] = WORD#16#FFFF THEN RETURN; END_IF;
IF (w类型 = 0) OR (w类型 = 2) THEN
    IF Store.aw气缸配置[缸号, 2] <> WORD#16#FFFF THEN RETURN; END_IF;
ELSE
    IF (Store.aw气缸配置[缸号, 2] = WORD#16#FFFF)
        OR (Store.aw气缸配置[缸号, 2] = Store.aw气缸配置[缸号, 1]) THEN RETURN; END_IF;
END_IF;
IF (Store.aw气缸配置[缸号, 6] = 0)
    OR (Store.aw气缸配置[缸号, 5] >= Store.aw气缸配置[缸号, 6])
    OR (Store.aw气缸配置[缸号, 7] >= Store.aw气缸配置[缸号, 6]) THEN RETURN; END_IF;
IF ((Store.aw气缸配置[缸号, 3] = WORD#16#FFFF) AND (Store.aw气缸配置[缸号, 5] = 0))
    OR ((Store.aw气缸配置[缸号, 4] = WORD#16#FFFF) AND (Store.aw气缸配置[缸号, 7] = 0)) THEN RETURN; END_IF;
IF (Store.aw气缸配置[缸号, 3] <> WORD#16#FFFF)
    AND (Store.aw气缸配置[缸号, 3] = Store.aw气缸配置[缸号, 4]) THEN RETURN; END_IF;
(* 同一物理地址只能属于一个已绑定气缸：输出和输入都查重，
   防止两个缸抢同一个阀或同一个端位传感器。 *)
FOR i := 0 TO 53 DO
    IF (i <> 缸号) AND ((lw已绑定气缸 AND SHL(LWORD#1, i)) <> 0) THEN
        (* DI与DO是独立地址空间：仅在同类映像内查重。 *)
        FOR j := 1 TO 2 DO
            FOR k := 1 TO 2 DO
                IF (Store.aw气缸配置[缸号, j] <> WORD#16#FFFF)
                    AND (Store.aw气缸配置[缸号, j] = Store.aw气缸配置[i, k]) THEN RETURN; END_IF;
            END_FOR;
        END_FOR;
        FOR j := 3 TO 4 DO
            FOR k := 3 TO 4 DO
                IF (Store.aw气缸配置[缸号, j] <> WORD#16#FFFF)
                    AND (Store.aw气缸配置[缸号, j] = Store.aw气缸配置[i, k]) THEN RETURN; END_IF;
            END_FOR;
        END_FOR;
    END_IF;
END_FOR;
气缸_配置有效 := TRUE;
END_FUNCTION
