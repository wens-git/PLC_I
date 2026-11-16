(* Volatile exchange. Call Server before installed axis consumers each scan.
   ConsumerMask proves program routing, never physical online or safety status. *)
TYPE 结构体_运行时 :
STRUCT
    ast轴 : ARRAY[0..15] OF 结构体_轴状态;
    aw轴命令 : ARRAY[0..15] OF WORD;
    aw轴序列 : ARRAY[0..15] OF WORD;
    adi轴目标 : ARRAY[0..15] OF DINT;
    audi轴速度 : ARRAY[0..15] OF UDINT;
    audi轴加速度 : ARRAY[0..15] OF UDINT;
    audi轴减速度 : ARRAY[0..15] OF UDINT;
    audi轴停止减速度 : ARRAY[0..15] OF UDINT;
    w轴消费掩码 : WORD;
    ast气缸 : ARRAY[0..53] OF 结构体_气缸状态;
    aw气缸命令 : ARRAY[0..53] OF WORD;
    aw气缸序列 : ARRAY[0..53] OF WORD;
    b手动 : BOOL;
    b运行 : BOOL;
    b暂停 : BOOL;
    bHMI在线 : BOOL;
    b复位中 : BOOL;
    (* 上位机命令 2/3/4 的一扫描事件。服务端在受理的同一扫描置位，
       PRG 在下一扫描消费后清零；与物理按钮沿分开，避免被 R_TRIG 合并。 *)
    b启动脉冲 : BOOL;
    b暂停脉冲 : BOOL;
    b恢复脉冲 : BOOL;
    b硬急停 : BOOL;
    b软急停 : BOOL;
    b待复位 : BOOL := TRUE;
    ui输入点数 : UINT;
    ui输出点数 : UINT;
    aw输入 : ARRAY[0..7] OF WORD;
    aw输出 : ARRAY[0..7] OF WORD;
END_STRUCT
END_TYPE
