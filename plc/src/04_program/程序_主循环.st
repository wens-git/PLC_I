(* Single owner task: Server -> pause orchestration -> each physical axis once.
   Modbus TCP is served by the official ModbusTCP_Slave_XJV1 device (port 1502);
   its process images 全局变量_通信映像.aw保持区/Input are exchanged by the IO
   update of this task. No SysSocket code, no custom listener.
   The only motion inhibit is the hard e-stop input and the software latch;
   there is no safety-commissioning gate.
   No legacy MAIN, old command path or legacy persistent state machine runs. *)
PROGRAM 程序_主循环
VAR
    fb服务端 : 功能块_服务端;
    fb运行 : 功能块_运行控制;
    fb暂停恢复 : 功能块_暂停恢复;
    fb轴请求监视 : 功能块_轴请求监视;
    fb启动滤波 : 功能块_输入滤波;
    fb暂停滤波 : 功能块_输入滤波;
    fb复位滤波 : 功能块_输入滤波;
    st运行时 : 结构体_运行时;
    fb轴0 : 功能块_轴;
    fb轴1 : 功能块_轴;
    fb轴2 : 功能块_轴;
    fb气缸调度 : 功能块_气缸调度;
    i循环 : UINT;
    b复位事件 : BOOL;
    b复位上周期 : BOOL;
    b急停 : BOOL;
    b设备报警 : BOOL;
    udi兜底 : UDINT;
END_VAR

(* 物理输入：启动/暂停/复位三路各按 20 ms 去抖（原程序同值）。
   急停输入不滤波：安全输入不进延时链，断线不可诊断，TRUE = 按下。 *)
fb启动滤波(b信号 := b输入0, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
fb暂停滤波(b信号 := b输入1, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
fb复位滤波(b信号 := b输入2, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
b复位事件 := fb复位滤波.b滤波信号 AND NOT b复位上周期;
b复位上周期 := fb复位滤波.b滤波信号;
b急停 := b输入3;

st运行时.w轴消费掩码 := 7;
st运行时.b硬急停 := b急停;
(* Only the verified physical input mapping is published. *)
st运行时.ui输入点数 := 5;
st运行时.ui输出点数 := 全局变量_运行配置.ui物理输出点数;
st运行时.aw输入[0] := BOOL_TO_WORD(b输入0) OR SHL(BOOL_TO_WORD(b输入1), 1)
    OR SHL(BOOL_TO_WORD(b输入2), 2) OR SHL(BOOL_TO_WORD(b输入3), 3)
    OR SHL(BOOL_TO_WORD(b输入4), 4);

fb服务端(Command := 全局变量_通信映像.aw保持区, Published := 全局变量_通信映像.aw发布区, Runtime := st运行时);

(* 停止减速度必须始终可下发：配置为 0 时按配置值兜底、仍为 0 则用 1 mm/s²。
   否则任何停止请求都会因为“没有减速度”被判无效。 *)
FOR i循环 := 0 TO 15 DO
    IF ((w已绑定轴 AND SHL(WORD#1, i循环)) <> 0)
    AND (st运行时.audi轴停止减速度[i循环] = 0) THEN
        udi兜底 := DWORD_TO_UDINT(SHL(WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 12]), 16)
            OR WORD_TO_DWORD(全局变量_保持区.Store.aw轴配置[i循环, 13]));
        IF udi兜底 = 0 THEN udi兜底 := 1; END_IF;
        st运行时.audi轴停止减速度[i循环] := udi兜底;
    END_IF;
END_FOR;

(* 运行状态机：物理按钮 + 上位机命令 2/3/4。命令 2 在
   b正式流程已接入 = FALSE 时仍由 函数_动作许可 拒绝为 12。 *)
b设备报警 := FALSE;
FOR i循环 := 0 TO 15 DO
    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN b设备报警 := b设备报警 OR st运行时.ast轴[i循环].b故障; END_IF;
END_FOR;
fb运行(b初始化完成 := TRUE,
    b系统复位完成 := NOT st运行时.b待复位,
    b系统复位中 := FALSE,
    b系统复位失败 := FALSE,
    b启动按钮 := fb启动滤波.b滤波信号,
    b暂停按钮 := fb暂停滤波.b滤波信号,
    b启动事件 := st运行时.b启动脉冲,
    b暂停事件 := st运行时.b暂停脉冲,
    (* 物理复位按钮与命令 4 等效：原程序“暂停中按复位进入暂停恢复”。 *)
    b恢复事件 := st运行时.b恢复脉冲 OR b复位事件,
    b致命报警 := st运行时.b硬急停 OR st运行时.b软急停 OR b设备报警,
    b急停 := b急停 OR st运行时.b软急停,
    b暂停报警 := b设备报警,
    b预警 := FALSE,
    b暂停恢复中 := fb暂停恢复.b恢复中,
    b暂停恢复完成 := fb暂停恢复.b恢复完成,
    b暂停恢复失败 := fb暂停恢复.b恢复失败,
    b流程完成 := FALSE);
st运行时.b运行 := fb运行.b运行指令;
st运行时.b暂停 := fb运行.b暂停中;
st运行时.b手动 := fb运行.b手动模式;
(* 命令 2/3/4 是一扫描事件：服务端本扫描置位，这里消费后立即清零，
   下一扫描不会重复触发。 *)
st运行时.b启动脉冲 := FALSE;
st运行时.b暂停脉冲 := FALSE;
st运行时.b恢复脉冲 := FALSE;

(* 暂停编排：必须在服务端之后，服务端每扫描开头清零命令数组。 *)
fb暂停恢复(b暂停 := fb运行.b暂停中, b请求 := fb运行.b暂停恢复请求,
    b急停 := b急停,
    di容差 := 全局变量_运行配置.di暂停恢复容差,
    di停稳ms := 全局变量_运行配置.di暂停停稳ms, Runtime := st运行时);

(* Cancel automatic requests before consumers when mode changes in this scan.
   Preserve existing stop/disable/reset pulses from the Server. *)
FOR i循环 := 0 TO 15 DO
    IF 全局变量_轴请求.ast请求[i循环].b忙
    AND 全局变量_轴请求.ast请求[i循环].b已下发
    AND (全局变量_轴请求.ast请求[i循环].w命令 <> 26)
    AND (NOT st运行时.b运行 OR st运行时.b暂停 OR NOT st运行时.bHMI在线
        OR st运行时.b硬急停 OR st运行时.b软急停
        OR st运行时.b待复位 OR st运行时.b复位中) THEN
        IF (st运行时.aw轴命令[i循环] = 0) OR (st运行时.aw轴命令[i循环] = 22)
        OR (st运行时.aw轴命令[i循环] = 27) THEN
            st运行时.aw轴命令[i循环] := 26;
        END_IF;
    END_IF;
END_FOR;

fb轴0(Axis := XJ_Axis0, State := st运行时.ast轴[0],
    OpenLoop := TRUE,
    Code := st运行时.aw轴命令[0], Sequence := st运行时.aw轴序列[0],
    Target := st运行时.adi轴目标[0], Speed := st运行时.audi轴速度[0],
    Acceleration := st运行时.audi轴加速度[0], Deceleration := st运行时.audi轴减速度[0],
    StopDeceleration := st运行时.audi轴停止减速度[0],
    HardEstop := st运行时.b硬急停,
    (* Pulse axes have no external presence/Ready feedback. *)
    PositiveLimit := ab正限位[0], NegativeLimit := ab负限位[0]);
fb轴1(Axis := XJ_Axis1, State := st运行时.ast轴[1],
    OpenLoop := TRUE,
    Code := st运行时.aw轴命令[1], Sequence := st运行时.aw轴序列[1],
    Target := st运行时.adi轴目标[1], Speed := st运行时.audi轴速度[1],
    Acceleration := st运行时.audi轴加速度[1], Deceleration := st运行时.audi轴减速度[1],
    StopDeceleration := st运行时.audi轴停止减速度[1],
    HardEstop := st运行时.b硬急停,
    PositiveLimit := ab正限位[1], NegativeLimit := ab负限位[1]);
fb轴2(Axis := BusMotionAxis, State := st运行时.ast轴[2],
    Code := st运行时.aw轴命令[2], Sequence := st运行时.aw轴序列[2],
    Target := st运行时.adi轴目标[2], Speed := st运行时.audi轴速度[2],
    Acceleration := st运行时.audi轴加速度[2], Deceleration := st运行时.audi轴减速度[2],
    StopDeceleration := st运行时.audi轴停止减速度[2],
    HardEstop := st运行时.b硬急停,
    PositiveLimit := ab正限位[2], NegativeLimit := ab负限位[2],
    BusOperational := BusAxis.wState = 8);
fb轴请求监视(Runtime := st运行时);
(* 统一单槽消费者在本扫描模式更新后复核许可。工程未绑定时不驱动。
   暂停保持夹持输出但关闭破真空；整机停止/急停/42撤销两输出。 *)
fb气缸调度(StopAll := fb服务端.StopAllRequested, Runtime := st运行时);

(* 未核验物理映射：不可把逻辑0/1偷偷绑定Y6/Y7。
   工程接线必须依据全局变量_气缸工程表明确连接真实IO及模块诊断。 *)
b输出6 := FALSE;
b输出7 := FALSE;
st运行时.aw输出[0] := BOOL_TO_WORD(b输出6) OR SHL(BOOL_TO_WORD(b输出7), 1);
END_PROGRAM
