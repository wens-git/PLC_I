(* 气缸输入映射：把物理输入换算成逻辑端位传感器，并推导"映射有效/模块就绪"。
   必须在 气缸调度 之前调用。本 POU 不产生任何输出驱动。
   两种来源：
     1) 扩展模块：按工程表点号从 aw气缸输入映像 读取（点号从 32 起）；
     2) 直连模式：少量气缸全接内建点，命名 BOOL 直接覆盖（见文件末尾）。 *)
PROGRAM 程序_气缸输入映射
VAR
    i : UINT;
    ui地址 : UINT;
    b模块就绪 : BOOL;
END_VAR

IF 全局变量_运行配置.b气缸IO模块诊断已接入 THEN
    b模块就绪 := b气缸输入模块在线 AND b气缸输出模块在线;
ELSE
    b模块就绪 := 全局变量_运行配置.b气缸IO已接入;
END_IF;

FOR i := 0 TO 53 DO
    ab气缸动点传感器[i] := FALSE;
    ab气缸原点传感器[i] := FALSE;
    ab气缸映射有效[i] := FALSE;
    IF (lw已绑定气缸 AND SHL(LWORD#1, i)) <> 0 THEN
        ab气缸映射有效[i] := 气缸_配置有效(缸号 := i, Store := 全局变量_保持区.Store);
        IF ab气缸映射有效[i] THEN
            ui地址 := WORD_TO_UINT(全局变量_保持区.Store.aw气缸配置[i, 3]);
            IF (ui地址 <> 65535) AND (ui地址 < ui气缸输入点数) THEN
                ab气缸动点传感器[i] :=
                    (aw气缸输入映像[ui地址 / 16] AND SHL(WORD#1, ui地址 MOD 16)) <> 0;
            END_IF;
            ui地址 := WORD_TO_UINT(全局变量_保持区.Store.aw气缸配置[i, 4]);
            IF (ui地址 <> 65535) AND (ui地址 < ui气缸输入点数) THEN
                ab气缸原点传感器[i] :=
                    (aw气缸输入映像[ui地址 / 16] AND SHL(WORD#1, ui地址 MOD 16)) <> 0;
            END_IF;
        END_IF;
    END_IF;
    ab气缸模块就绪[i] := b模块就绪;
END_FOR;

(* ===== 直连模式：命名传感器 -> 驱动数组 =====
   加直连缸时在此加对应行，并同步 程序_气缸输出映射 与 全局变量_气缸工程。 *)
ab气缸动点传感器[0] := bCY00_动点传感器;
ab气缸原点传感器[0] := bCY00_原点传感器;
ab气缸动点传感器[1] := bCY01_动点传感器;
END_PROGRAM
