(* 物理输入/输出边界。地址来自信捷 HSIO Byte0/Byte1 实测映射。
   X0..X4 = %IX0.0..%IX0.4；Y6/Y7 = %QX0.6..%QX0.7。
   Y0/Y1 是 XJ_Axis0 的脉冲/方向输出，禁止复用为指示灯。 *)
VAR_GLOBAL
    b输入0 AT %IX0.0 : BOOL;  (* 启动，高有效 *)
    b输入1 AT %IX0.1 : BOOL;  (* 暂停，高有效 *)
    b输入2 AT %IX0.2 : BOOL;  (* 复位，高有效 *)
    b输入3 AT %IX0.3 : BOOL;  (* 急停常开；TRUE 表示按下，断线不可诊断 *)
    b输入4 AT %IX0.4 : BOOL;  (* 备用，高有效 *)
    b输出6 AT %QX0.6 : BOOL;
    b输出7 AT %QX0.7 : BOOL;
END_VAR
