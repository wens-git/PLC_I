(* 唯一消费者：在服务端及本扫描模式更新之后运行。 *)
FUNCTION_BLOCK 功能块_气缸调度
VAR_INPUT StopAll : BOOL; END_VAR
VAR_IN_OUT Runtime : 结构体_运行时; END_VAR
VAR
    afb驱动 : ARRAY[0..53] OF 功能块_气缸;
    i : UINT;
    by取消 : BYTE;
    w许可 : WORD;
    b执行 : BOOL;
    b绑定 : BOOL;
    b动点传感器 : BOOL;
    b原点传感器 : BOOL;
END_VAR
FOR i := 0 TO 53 DO
    b绑定 := (lw已绑定气缸 AND SHL(LWORD#1, i)) <> 0;
    by取消 := 0;
    IF Runtime.b暂停 THEN by取消 := 1; END_IF;
    IF NOT Runtime.bHMI在线 OR Runtime.b待复位 OR Runtime.b复位中
        OR (全局变量_气缸请求.ast请求[i].b自动 AND (NOT Runtime.b运行 OR Runtime.b手动))
        OR (NOT 全局变量_气缸请求.ast请求[i].b自动 AND NOT Runtime.b手动) THEN
        by取消 := 1;
    END_IF;
    IF StopAll OR NOT b绑定 OR NOT ab气缸映射已核验[i] OR NOT ab气缸模块就绪[i]
        OR Runtime.b硬急停 OR Runtime.b软急停 THEN by取消 := 2; END_IF;
    b执行 := 全局变量_气缸请求.ast请求[i].b待下发;
    (* 停止不受模式取消阻挡，始终能撤销输出并确认已消失的故障。 *)
    IF b执行 AND (全局变量_气缸请求.ast请求[i].w命令 <> 42) THEN
        w许可 := 函数_动作许可(Code := 全局变量_气缸请求.ast请求[i].w命令,
            ObjectWord := WORD#16#0200 OR UINT_TO_WORD(i), HmiOnline := Runtime.bHMI在线,
            JogBusy := FALSE, Resetting := Runtime.b复位中,
            b自动请求 := 全局变量_气缸请求.ast请求[i].b自动, b气缸已受理 := TRUE,
            Runtime := Runtime, Store := 全局变量_保持区.Store);
        IF w许可 <> 0 THEN
            b执行 := FALSE;
            全局变量_气缸请求.ast请求[i].w错误 := w许可;
            IF by取消 = 0 THEN by取消 := 1; END_IF;
        END_IF;
    END_IF;
    b动点传感器 := 全局变量_保持区.Store.aw气缸配置[i, 3] <> WORD#16#FFFF;
    b原点传感器 := 全局变量_保持区.Store.aw气缸配置[i, 4] <> WORD#16#FFFF;
    afb驱动[i](Execute := b执行, Token := 全局变量_气缸请求.ast请求[i].udi请求号,
        Code := 全局变量_气缸请求.ast请求[i].w命令,
        SensorWork := b动点传感器 AND (ab气缸动点传感器[i] XOR ((全局变量_保持区.Store.aw气缸配置[i, 0] AND 4) <> 0)),
        SensorOrigin := b原点传感器 AND (ab气缸原点传感器[i] XOR ((全局变量_保持区.Store.aw气缸配置[i, 0] AND 8) <> 0)),
        HasWorkSensor := b动点传感器, HasOriginSensor := b原点传感器,
        DelayMs := 全局变量_保持区.Store.aw气缸配置[i, 5], HomeDelayMs := 全局变量_保持区.Store.aw气缸配置[i, 7],
        TimeoutMs := 全局变量_保持区.Store.aw气缸配置[i, 6],
        ValveType := WORD_TO_BYTE(全局变量_保持区.Store.aw气缸配置[i, 0] AND 3),
        HardEstop := Runtime.b硬急停 OR Runtime.b软急停, CancelMode := by取消);
    全局变量_气缸请求.ast请求[i].b待下发 := FALSE;
    IF (by取消 <> 0) OR afb驱动[i].Fault OR (b执行 AND (全局变量_气缸请求.ast请求[i].w命令 = 42)) THEN
        全局变量_气缸请求.ast请求[i].b忙 := FALSE;
        全局变量_气缸请求.ast请求[i].udi完成号 := 0;
        IF afb驱动[i].Fault THEN 全局变量_气缸请求.ast请求[i].w错误 := afb驱动[i].Error;
        ELSIF 全局变量_气缸请求.ast请求[i].w错误 = 0 THEN 全局变量_气缸请求.ast请求[i].w错误 := 19;
        END_IF;
    ELSIF (afb驱动[i].DoneToken <> 0) AND (afb驱动[i].DoneToken = 全局变量_气缸请求.ast请求[i].udi请求号) THEN
        全局变量_气缸请求.ast请求[i].udi完成号 := afb驱动[i].DoneToken;
        全局变量_气缸请求.ast请求[i].b忙 := FALSE;
    END_IF;
    Runtime.ast气缸[i].b在动点 := afb驱动[i].AtWork;
    Runtime.ast气缸[i].b在原点 := afb驱动[i].AtOrigin;
    Runtime.ast气缸[i].b运动中 := afb驱动[i].Moving;
    Runtime.ast气缸[i].b故障 := afb驱动[i].Fault;
    Runtime.ast气缸[i].w错误码 := afb驱动[i].Error;
    ab气缸动点输出[i] := b绑定 AND ab气缸映射已核验[i] AND ab气缸模块就绪[i] AND afb驱动[i].WorkOutput;
    ab气缸原点输出[i] := b绑定 AND ab气缸映射已核验[i] AND ab气缸模块就绪[i] AND afb驱动[i].OriginOutput;
END_FOR;
全局变量_气缸请求.st许可快照 := Runtime;
END_FUNCTION_BLOCK
