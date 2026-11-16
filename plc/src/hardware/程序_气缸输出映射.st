(* 气缸输出映射：把调度产生的逻辑阀需求写到物理输出。
   必须在 气缸调度 之后调用。两种去向：
     1) 扩展模块：按工程表点号写 aw气缸输出映像（点号从 32 起）；
     2) 直连模式：少量气缸全接内建点，直接驱动命名阀（见文件末尾）。 *)
PROGRAM 程序_气缸输出映射
VAR
    i : UINT;
    ui地址 : UINT;
END_VAR

FOR i := 0 TO 3 DO
    aw气缸输出映像[i] := 0;
END_FOR;
FOR i := 0 TO 53 DO
    IF (lw已绑定气缸 AND SHL(LWORD#1, i)) <> 0
        AND ab气缸映射有效[i] AND ab气缸模块就绪[i] THEN
        ui地址 := WORD_TO_UINT(全局变量_保持区.Store.aw气缸配置[i, 1]);
        IF (ui地址 <> 65535) AND (ui地址 < ui气缸输出点数)
            AND ab气缸动点输出[i] THEN
            aw气缸输出映像[ui地址 / 16] :=
                aw气缸输出映像[ui地址 / 16] OR SHL(WORD#1, ui地址 MOD 16);
        END_IF;
        ui地址 := WORD_TO_UINT(全局变量_保持区.Store.aw气缸配置[i, 2]);
        IF (ui地址 <> 65535) AND (ui地址 < ui气缸输出点数)
            AND ab气缸原点输出[i] THEN
            aw气缸输出映像[ui地址 / 16] :=
                aw气缸输出映像[ui地址 / 16] OR SHL(WORD#1, ui地址 MOD 16);
        END_IF;
    END_IF;
END_FOR;

(* ===== 直连模式：驱动数组 -> 命名阀（Y2/Y3/Y6/Y7）=====
   未绑定或映射无效时数组为 FALSE，阀输出为 0。加直连缸时在此加对应行。 *)
bCY00_动点阀 := ab气缸动点输出[0];
bCY00_原点阀 := ab气缸原点输出[0];
bCY01_动点阀 := ab气缸动点输出[1];
bCY01_原点阀 := ab气缸原点输出[1];
END_PROGRAM
