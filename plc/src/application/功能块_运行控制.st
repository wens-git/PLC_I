(* 整机运行状态机。移植自原程序 功能块_运行控制 + 子程序_运行管理__暂停恢复
   的进入/退出部分，语义逐条对齐：
   优先级 硬故障 > 流程完成 > 初始化/复位 > 暂停 > 启动；
   同一扫描启动与暂停同时出现时暂停优先；
   自动启动必须先通过 b自动可运行（初始化、复位完成、无致命报警、无暂停恢复中）。
   本块只产生“模式与运行指令”，不产生任何动作许可；动作许可仍由
   函数_动作许可 单层判定。 *)
FUNCTION_BLOCK 功能块_运行控制
VAR_INPUT
    b初始化完成 : BOOL;
    b系统复位完成 : BOOL;
    b系统复位中 : BOOL;
    b系统复位失败 : BOOL;
    (* 物理按钮电平（已去抖）。 *)
    b启动按钮 : BOOL;
    b暂停按钮 : BOOL;
    (* 上位机命令 2/3/4 已由 SEQ 去重，是独立的一扫描事件，
       不能与物理电平共用 R_TRIG，否则连续两帧命令会被合并。 *)
    b启动事件 : BOOL;
    b暂停事件 : BOOL;
    b恢复事件 : BOOL;
    b致命报警 : BOOL;
    b急停 : BOOL;
    b暂停报警 : BOOL;
    b预警 : BOOL;
    (* 由回收器回写：恢复进度与结果。 *)
    b暂停恢复中 : BOOL;
    b暂停恢复完成 : BOOL;
    b暂停恢复失败 : BOOL;
    b流程完成 : BOOL;
END_VAR
VAR_OUTPUT
    b运行指令 : BOOL;
    b期望运行 : BOOL;
    b暂停中 : BOOL;
    b自动模式 : BOOL;
    b手动模式 : BOOL;
    b自动可运行 : BOOL;
    (* 电平请求：置位启动暂停恢复，恢复完成后由本块清除。 *)
    b暂停恢复请求 : BOOL;
    b报警灯 : BOOL;
    b运行灯 : BOOL;
    b待机灯 : BOOL;
END_VAR
VAR
    rt启动 : R_TRIG;
    rt暂停 : R_TRIG;
END_VAR

rt启动(CLK := b启动按钮);
rt暂停(CLK := b暂停按钮);

b报警灯 := b致命报警 OR b暂停报警 OR b预警;
b自动可运行 := b初始化完成
    AND b系统复位完成
    AND NOT b系统复位中
    AND NOT b系统复位失败
    AND NOT b致命报警
    AND NOT b暂停恢复中
    AND NOT b暂停恢复失败;

(* 优先级：硬故障 > 流程完成 > 初始化/复位 > 暂停 > 启动。 *)
IF b致命报警 THEN
    b运行指令 := FALSE;
    b期望运行 := FALSE;
    b暂停中 := FALSE;
    b暂停恢复请求 := FALSE;
ELSIF b流程完成 THEN
    b运行指令 := FALSE;
    b期望运行 := FALSE;
    b暂停中 := FALSE;
    b暂停恢复请求 := FALSE;
ELSIF (NOT b初始化完成) OR (NOT b系统复位完成) THEN
    b运行指令 := FALSE;
    b期望运行 := FALSE;
    b暂停中 := FALSE;
    b暂停恢复请求 := FALSE;
ELSIF b系统复位中 OR b系统复位失败 THEN
    b运行指令 := FALSE;
    b期望运行 := FALSE;
    b暂停中 := FALSE;
    b暂停恢复请求 := FALSE;
ELSE
    (* 暂停恢复是一次性握手：请求 -> 恢复中 -> 完成/失败。
       恢复期间保持请求电平，完成或失败后立即撤销，不会重复触发。 *)
    IF b暂停恢复失败 THEN
        b暂停恢复请求 := FALSE;
        IF NOT b暂停恢复中 THEN b暂停中 := TRUE; END_IF;
    ELSIF b暂停恢复完成 AND b暂停恢复请求 AND NOT b暂停恢复中 THEN
        b暂停恢复请求 := FALSE;
        b暂停中 := FALSE;
        b运行指令 := TRUE;
        b期望运行 := TRUE;
    END_IF;

    IF NOT b暂停恢复请求 AND NOT b暂停恢复中 THEN
        IF rt暂停.Q OR b暂停事件 THEN
            IF b运行指令 THEN
                b运行指令 := FALSE;
                b暂停中 := TRUE;
            END_IF;
        (* 同一扫描启动和暂停同时出现时，暂停优先。
           暂停中不接受启动：暂停必须经命令 4 的受控恢复退出，
           否则会绕过暂停快照回位直接重新运行。 *)
        ELSIF (rt启动.Q OR b启动事件)
        AND NOT b暂停中
        AND b自动可运行
        AND NOT b暂停报警 THEN
            b期望运行 := TRUE;
            b运行指令 := TRUE;
            b暂停中 := FALSE;
        (* 命令 4：暂停中的受控恢复请求。 *)
        ELSIF b恢复事件 AND b暂停中 AND b自动可运行 AND NOT b暂停报警 THEN
            b暂停恢复请求 := TRUE;
        END_IF;
    END_IF;

    (* 急停在任何恢复阶段都立即撤销请求；恢复结果由回收器置失败。 *)
    IF b急停 THEN b暂停恢复请求 := FALSE; END_IF;
END_IF;

(* 模式只描述当前控制归属，不代表动作已经获得安全许可。 *)
b自动模式 := b运行指令;
b手动模式 := NOT b运行指令 AND NOT b急停;
b运行灯 := b运行指令;
b待机灯 := NOT b运行指令 AND NOT b报警灯;
END_FUNCTION_BLOCK
