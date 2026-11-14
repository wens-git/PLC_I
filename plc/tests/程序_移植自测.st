(* 移植块的行为自测：功能块_输入滤波 / 功能块_运行控制 / 功能块_暂停恢复。
   纯逻辑，不调用 MC，不写物理输出，在隔离仿真器中运行。

   暂停恢复用独立实例、显式输入直接驱动，不经运行状态机：
   每个断言的因果都落在同一个块内，不依赖两个块之间的扫描时序。
   停稳时间用 di停稳ms 参数化，自测取 10 ms，现场仍是 300 ms。 *)
PROGRAM 程序_移植自测
VAR
    fb滤波 : 功能块_输入滤波;
    fb运行 : 功能块_运行控制;
    fb暂停 : 功能块_暂停恢复;
    st运行时 : 结构体_运行时;
    ui阶段 : UINT;
    i循环 : UINT;
    b正常 : BOOL;
    b检查 : BOOL;
    b等待中 : BOOL;
    b首次进入 : BOOL;
    b恢复请求脉冲已发 : BOOL;
    tmr等待 : TON;
    udi通过 : UDINT;
    udi失败 : UDINT;
    ui首失败 : UINT;
    b完成 : BOOL;
    b滤波输入 : BOOL;
    (* 暂停恢复的显式驱动输入。 *)
    b暂停请求 : BOOL;
    b恢复请求 : BOOL;
    b急停测试 : BOOL;
    w诊断1 : WORD;
    w诊断2 : WORD;
END_VAR

IF b完成 THEN RETURN; END_IF;
b检查 := FALSE;
b正常 := TRUE;

(* 运行控制每扫描连续调用；暂停恢复由 b暂停请求 / b恢复请求 直接驱动。 *)
fb运行(b初始化完成 := TRUE,
    b系统复位完成 := TRUE,
    b系统复位中 := FALSE,
    b系统复位失败 := FALSE,
    b启动按钮 := FALSE,
    b暂停按钮 := FALSE,
    b启动事件 := st运行时.b启动脉冲,
    b暂停事件 := st运行时.b暂停脉冲,
    b恢复事件 := st运行时.b恢复脉冲,
    b致命报警 := FALSE,
    b急停 := FALSE,
    b暂停报警 := FALSE,
    b预警 := FALSE,
    b暂停恢复中 := FALSE,
    b暂停恢复完成 := FALSE,
    b暂停恢复失败 := FALSE,
    b流程完成 := FALSE);
st运行时.b启动脉冲 := FALSE;
st运行时.b暂停脉冲 := FALSE;
st运行时.b恢复脉冲 := FALSE;

fb暂停(b暂停 := b暂停请求, b请求 := b恢复请求,
    b急停 := b急停测试,
    di容差 := 100, di停稳ms := 10, Runtime := st运行时);

(* 等待解除：条件满足或超时都只做一次“解除 b等待中”，推进交给扫描末尾统一处理。
   这样每个扫描最多推进一次，阶段体不会重复执行，也不会漏推进。 *)
tmr等待(IN := b等待中, PT := T#500ms);
IF b等待中 THEN
    IF (ui阶段 = 10) AND fb暂停.b已抓拍 THEN b等待中 := FALSE;
    ELSIF (ui阶段 = 16) AND (st运行时.aw轴命令[0] = 27) THEN b等待中 := FALSE;
    ELSIF (ui阶段 = 18) AND (fb暂停.b恢复完成 OR fb暂停.b恢复失败) THEN b等待中 := FALSE;
    ELSIF tmr等待.Q THEN b等待中 := FALSE;
    END_IF;
END_IF;
(* b等待中 只由阶段体在“首次进入”时置位，由上面的条件或 500 ms 超时解除；
   扫描末尾按它的值决定是否推进，因此每个扫描最多推进一次。 *)

w诊断1 := fb暂停.ui内部阶段 * 256;
IF fb暂停.b已抓拍 THEN w诊断1 := w诊断1 OR 2; END_IF;
IF fb暂停.b曾偏离 THEN w诊断1 := w诊断1 OR 4; END_IF;
IF fb暂停.b恢复中 THEN w诊断1 := w诊断1 OR 8; END_IF;
IF fb暂停.b恢复完成 THEN w诊断1 := w诊断1 OR 16; END_IF;
IF fb暂停.b恢复失败 THEN w诊断1 := w诊断1 OR 32; END_IF;
w诊断2 := 0;
IF st运行时.aw轴命令[0] = 27 THEN w诊断2 := w诊断2 OR 1; END_IF;
IF st运行时.aw轴命令[0] = 26 THEN w诊断2 := w诊断2 OR 2; END_IF;

CASE ui阶段 OF
    (* ===== 输入滤波 ===== *)
    0:
        b滤波输入 := TRUE;
        fb滤波(b信号 := b滤波输入, i模式 := 0,
            di滤波时间真 := 20, di滤波时间假 := 20);
        b检查 := TRUE; b正常 := fb滤波.b滤波信号;
    1:
        (* 模式 1：输入变 FALSE，20 ms 未到，输出保持上一扫描的 TRUE。 *)
        b滤波输入 := FALSE;
        fb滤波(b信号 := b滤波输入, i模式 := 1,
            di滤波时间真 := 20, di滤波时间假 := 20);
        b检查 := TRUE; b正常 := fb滤波.b滤波信号;
    2:
        (* 非法模式按直通，不把输入锁死。 *)
        b滤波输入 := TRUE;
        fb滤波(b信号 := b滤波输入, i模式 := 99,
            di滤波时间真 := 20, di滤波时间假 := 20);
        b检查 := TRUE; b正常 := fb滤波.b滤波信号;

    (* ===== 运行控制 ===== *)
    3:
        b检查 := TRUE;
        b正常 := fb运行.b手动模式 AND NOT fb运行.b运行指令 AND NOT fb运行.b暂停中;
    4:
        st运行时.b启动脉冲 := TRUE;
    5:
        b检查 := TRUE;
        b正常 := fb运行.b运行指令 AND NOT fb运行.b暂停中 AND fb运行.b自动模式;
    6:
        st运行时.b暂停脉冲 := TRUE;
    7:
        b检查 := TRUE; b正常 := (NOT fb运行.b运行指令) AND fb运行.b暂停中;
    8:
        (* 暂停优先于启动：暂停中收到启动不得运行。 *)
        st运行时.b启动脉冲 := TRUE;
    9:
        b检查 := TRUE; b正常 := (NOT fb运行.b运行指令) AND fb运行.b暂停中;

    (* ===== 暂停恢复：直接驱动 ===== *)
    10:
        (* 三轴静止于 1000，无急停，进入暂停。
           进入后立刻布置等待；阶段体不再重复执行，避免每扫描重置等待。 *)
        IF b首次进入 THEN
        b首次进入 := FALSE;
        b等待中 := TRUE;
        st运行时.w轴消费掩码 := 7;
        b急停测试 := FALSE;
        b恢复请求 := FALSE;
        FOR i循环 := 0 TO 2 DO
            st运行时.ast轴[i循环].b在线 := TRUE;
            st运行时.ast轴[i循环].b静止 := TRUE;
            st运行时.ast轴[i循环].b运动中 := FALSE;
            st运行时.ast轴[i循环].b故障 := FALSE;
            st运行时.ast轴[i循环].di位置 := 1000;
            st运行时.ast轴[i循环].w序列 := 0;
            st运行时.ast轴[i循环].w运动结果 := 0;
        END_FOR;
        b暂停请求 := TRUE;
        END_IF;
    11:
        (* 停稳 10 ms 后必须抓到快照。 *)
        b检查 := TRUE; b正常 := fb暂停.b已抓拍;
    12:
        (* 未偏离时请求恢复。恢复请求是上升沿事件，置位一个扫描即撤销。 *)
        b恢复请求 := TRUE;
    13:
        b恢复请求 := FALSE;
        b检查 := TRUE;
        b正常 := fb暂停.b恢复完成 AND NOT fb暂停.b恢复失败 AND (st运行时.aw轴命令[0] = 0);
    14:
        (* 拉开轴 0 超出容差 100：应锁存曾偏离。 *)
        b恢复请求 := FALSE;
        st运行时.ast轴[0].di位置 := 2000;
    15:
        b检查 := TRUE; b正常 := fb暂停.b曾偏离;
    16:
        (* 请求恢复：应给轴 0 下发绝对定位 27 回快照位置 1000。 *)
        IF b首次进入 THEN
        b首次进入 := FALSE;
        b等待中 := TRUE;
        st运行时.ast轴[0].w序列 := 0;
        st运行时.ast轴[0].w运动结果 := 0;
        b恢复请求 := TRUE;
        END_IF;
        (* 恢复请求只在一个扫描为真：等待结束后下一扫描即撤销。 *)
        IF b恢复请求脉冲已发 THEN b恢复请求 := FALSE; b恢复请求脉冲已发 := FALSE; END_IF;
        IF b恢复请求 THEN b恢复请求脉冲已发 := TRUE; END_IF;
    17:
        b检查 := TRUE;
        b正常 := (st运行时.aw轴命令[0] = 27) AND (st运行时.adi轴目标[0] = 1000);
    18:
        (* 轴报告结果 2 且静止：恢复完成。 *)
        st运行时.ast轴[0].w序列 := st运行时.aw轴序列[0];
        st运行时.ast轴[0].w运动结果 := 2;
        st运行时.ast轴[0].di位置 := 1000;
        IF b首次进入 THEN
        b首次进入 := FALSE;
        b等待中 := TRUE;
        st运行时.ast轴[0].b静止 := TRUE;
        st运行时.ast轴[0].b运动中 := FALSE;
        END_IF;
    19:
        b检查 := TRUE; b正常 := fb暂停.b恢复完成 AND NOT fb暂停.b恢复失败;
    20:
        (* 急停：必须封锁并撤销本块下发的命令。 *)
        b恢复请求 := FALSE;
        st运行时.ast轴[0].di位置 := 3000;
        b急停测试 := TRUE;
    21: ;
    22:
        b检查 := TRUE; b正常 := st运行时.aw轴命令[0] = 0;
    23:
        b完成 := TRUE;
END_CASE;

IF b检查 THEN
    IF b正常 THEN udi通过 := udi通过 + 1;
    ELSE
        udi失败 := udi失败 + 1;
        IF ui首失败 = 0 THEN ui首失败 := ui阶段; END_IF;
    END_IF;
END_IF;
(* b等待中 可能在阶段体内刚被置位，这里同时看两个标志，避免立即推进。 *)
(* 每个扫描最多推进一次。阶段体若在本扫描刚置 b等待中，就保持不动。 *)
IF NOT b等待中 THEN ui阶段 := ui阶段 + 1; b首次进入 := TRUE; END_IF;
END_PROGRAM
