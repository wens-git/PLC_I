(* 模式/暂停恢复的唯一状态拥有者。服务端之后、轴组之前调用一次。 *)
FUNCTION_BLOCK 功能块_模式管理
VAR_INPUT StartButton : BOOL; PauseButton : BOOL; ResetButton : BOOL; END_VAR
VAR_IN_OUT Runtime : 结构体_运行时; END_VAR
VAR
    fb运行 : 功能块_运行控制;
    fb暂停恢复 : 功能块_暂停恢复;
    fb启动滤波 : 功能块_输入滤波;
    fb暂停滤波 : 功能块_输入滤波;
    fb复位滤波 : 功能块_输入滤波;
    b复位事件 : BOOL;
    b复位上周期 : BOOL;
    b设备报警 : BOOL;
    b急停 : BOOL;
    i循环 : UINT;
END_VAR
fb启动滤波(b信号 := StartButton, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
fb暂停滤波(b信号 := PauseButton, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
fb复位滤波(b信号 := ResetButton, i模式 := 1,
    di滤波时间真 := 全局变量_运行配置.di输入滤波时间ms,
    di滤波时间假 := 全局变量_运行配置.di输入滤波时间ms);
b复位事件 := fb复位滤波.b滤波信号 AND NOT b复位上周期;
b复位上周期 := fb复位滤波.b滤波信号;
b急停 := Runtime.b硬急停;
(* ===== 区域 3：运行模式与命令脉冲消费 ===== *)
(* 运行状态机：物理按钮 + 上位机命令 2/3/4。命令 2 在
   b正式流程已接入 = FALSE 时仍由 函数_动作许可 拒绝为 12。 *)
b设备报警 := FALSE;
FOR i循环 := 0 TO 15 DO
    IF (w已绑定轴 AND SHL(WORD#1, i循环)) <> 0 THEN b设备报警 := b设备报警 OR Runtime.ast轴[i循环].b故障; END_IF;
END_FOR;
fb运行(b初始化完成 := TRUE,
    b系统复位完成 := NOT Runtime.b待复位,
    b系统复位中 := FALSE,
    b系统复位失败 := FALSE,
    b启动按钮 := fb启动滤波.b滤波信号 AND 全局变量_运行配置.b正式流程已接入,
    b暂停按钮 := fb暂停滤波.b滤波信号,
    b启动事件 := Runtime.b启动脉冲,
    b暂停事件 := Runtime.b暂停脉冲,
    (* 物理复位按钮与命令 4 等效：原程序“暂停中按复位进入暂停恢复”。 *)
    b恢复事件 := Runtime.b恢复脉冲 OR (b复位事件 AND 全局变量_运行配置.b正式流程已接入),
    b致命报警 := Runtime.b硬急停 OR Runtime.b软急停 OR b设备报警,
    b急停 := b急停 OR Runtime.b软急停,
    b暂停报警 := b设备报警,
    b预警 := FALSE,
    b暂停恢复中 := fb暂停恢复.b恢复中,
    b暂停恢复完成 := fb暂停恢复.b恢复完成,
    b暂停恢复失败 := fb暂停恢复.b恢复失败,
    b流程完成 := FALSE);
Runtime.b运行 := fb运行.b运行指令;
Runtime.b暂停 := fb运行.b暂停中;
Runtime.b手动 := fb运行.b手动模式;
(* 命令 2/3/4 是一扫描事件：服务端本扫描置位，这里消费后立即清零，
   下一扫描不会重复触发。 *)
Runtime.b启动脉冲 := FALSE;
Runtime.b暂停脉冲 := FALSE;
Runtime.b恢复脉冲 := FALSE;

(* 暂停编排：必须在服务端之后，服务端每扫描开头清零命令数组。 *)
fb暂停恢复(b暂停 := fb运行.b暂停中, b请求 := fb运行.b暂停恢复请求,
    b急停 := b急停,
    di容差 := 全局变量_运行配置.di暂停恢复容差,
    di停稳ms := 全局变量_运行配置.di暂停停稳ms, Runtime := Runtime);

(* Cancel automatic requests before consumers when mode changes in this scan.
   Preserve existing stop/disable/reset pulses from the Server. *)
FOR i循环 := 0 TO 15 DO
    IF 全局变量_轴请求.ast请求[i循环].b忙
    AND 全局变量_轴请求.ast请求[i循环].b已下发
    AND (全局变量_轴请求.ast请求[i循环].w命令 <> 26)
    AND (NOT Runtime.b运行 OR Runtime.b暂停 OR NOT Runtime.bHMI在线
        OR Runtime.b硬急停 OR Runtime.b软急停
        OR Runtime.b待复位 OR Runtime.b复位中) THEN
        IF (Runtime.aw轴命令[i循环] = 0) OR (Runtime.aw轴命令[i循环] = 22)
        OR (Runtime.aw轴命令[i循环] = 27) THEN
            Runtime.aw轴命令[i循环] := 26;
        END_IF;
    END_IF;
END_FOR;

END_FUNCTION_BLOCK
