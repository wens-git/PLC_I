(* 唯一周期入口：明确扫描顺序，业务状态分别由各FB拥有。
   PLC_PRG在4ms EtherCAT_Task中仅调用本程序一次。 *)
PROGRAM 程序_主循环
VAR
    fb服务端 : 功能块_服务端;
    fb模式 : 功能块_模式管理;
    fb轴组 : 功能块_轴组;
    fb气缸调度 : 功能块_气缸调度;
    st运行时 : 结构体_运行时;
END_VAR

(* 1 工程绑定和物理输入快照；安全输入不经软件滤波。
   aw输入[0] 的 bit0..bit4 依次对应 X0..X4（协议 I/O 窗口按此位序发布）。 *)
程序_气缸绑定();
st运行时.w轴消费掩码 := 7;
st运行时.b硬急停 := b急停按钮;
st运行时.ui输入点数 := 5;
st运行时.ui输出点数 := 全局变量_运行配置.ui物理输出点数;
st运行时.aw输入[0] := BOOL_TO_WORD(b启动按钮)
    OR SHL(BOOL_TO_WORD(b暂停按钮), 1)
    OR SHL(BOOL_TO_WORD(b复位按钮), 2)
    OR SHL(BOOL_TO_WORD(b急停按钮), 3)
    OR SHL(BOOL_TO_WORD(b备用输入), 4);

(* 2 通信事务与系统请求；3 当前模式/暂停恢复；4 物理轴唯一消费者。 *)
fb服务端(Command := 全局变量_通信映像.aw保持区,
    Published := 全局变量_通信映像.aw发布区, Runtime := st运行时);
fb模式(StartButton := b启动按钮, PauseButton := b暂停按钮, ResetButton := b复位按钮, Runtime := st运行时);
fb轴组(Runtime := st运行时);

(* 5 气缸输入 -> 调度 -> 输出（内建直连点和扩展映像都在两个映射程序内）。 *)
程序_气缸输入映射();
fb气缸调度(StopAll := fb服务端.StopAllRequested, Runtime := st运行时);
程序_气缸输出映射();
(* HMI 的 Y0/Y1 分别对应物理 Y6/Y7（当前模板接 CY01 两路阀）。 *)
st运行时.aw输出[0] := BOOL_TO_WORD(bCY01_动点阀) OR SHL(BOOL_TO_WORD(bCY01_原点阀), 1);
END_PROGRAM
