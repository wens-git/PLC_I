(* 气缸物理 IO 映像。设备树把扩展输入/输出模块映射到本数组后，
   由 程序_气缸输入映射 / 程序_气缸输出映射 按工程表地址读写。
   容量：输入 112 点(7 WORD)，输出 56 点(4 WORD)。
   未映射时数组保持 0，模块在线位保持 FALSE，气缸许可因此关闭。 *)
VAR_GLOBAL CONSTANT
    ui气缸输入点数 : UINT := 112;
    ui气缸输出点数 : UINT := 56;
END_VAR
VAR_GLOBAL
    aw气缸输入映像 : ARRAY[0..6] OF WORD;
    aw气缸输出映像 : ARRAY[0..3] OF WORD;
    (* 真实模块诊断：由设备树/总线诊断赋值，不得用工程常量冒充。 *)
    b气缸输入模块在线 : BOOL;
    b气缸输出模块在线 : BOOL;
END_VAR
