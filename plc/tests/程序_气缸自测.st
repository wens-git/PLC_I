(* 离线IEC扫描自测：放入周期任务，等待b完成，w失败=0才通过。
   不连接物理输出。TON时间证据要求在目标PLC/官方模拟运行，源码测试不能替代。 *)
PROGRAM 程序_气缸自测
VAR
    fb : 功能块_气缸;
    fb原点 : 功能块_气缸;
    ui阶段 : UINT;
    w失败 : WORD;
    b完成 : BOOL;
    t等待 : TON;
    st配置 : 结构体_配置;
    fb调度 : 功能块_气缸调度;
    st运行时 : 结构体_运行时;
    lw原绑定 : LWORD;
    i : UINT;
    udi夹紧请求号 : UDINT; (* 业务示例：保存 Cy动点(Cy夹紧) 返回值 *)
END_VAR
CASE ui阶段 OF
0:
    fb(Execute := FALSE, Token := 0, Code := 0, HasWorkSensor := FALSE, HasOriginSensor := FALSE,
        DelayMs := 20, HomeDelayMs := 30, TimeoutMs := 500, ValveType := 3, HardEstop := FALSE, CancelMode := 0);
    IF fb.AtWork OR fb.AtOrigin OR (fb.DoneToken <> 0) THEN w失败 := 1; END_IF;
    ui阶段 := 1;
1:
    fb(Execute := TRUE, Token := 1, Code := 40);
    IF NOT fb.WorkOutput OR fb.OriginOutput THEN w失败 := 2; END_IF;
    IF fb.DoneToken = 1 THEN ui阶段 := 2; END_IF;
2:
    (* Execute连续TRUE，下一扫描新token仍触发反向请求。 *)
    fb(Execute := TRUE, Token := 2, Code := 41);
    IF fb.WorkOutput OR NOT fb.OriginOutput OR fb.AtWork OR (fb.DoneToken <> 0) THEN w失败 := 3; END_IF;
    ui阶段 := 3;
3:
    fb(Execute := FALSE);
    IF fb.DoneToken = 2 THEN
        IF fb.OriginOutput OR NOT fb.AtOrigin THEN w失败 := 4; END_IF;
        ui阶段 := 4;
    END_IF;
4:
    fb(Execute := TRUE, Token := 3, Code := 40);
    ui阶段 := 5;
5:
    fb(Execute := FALSE, CancelMode := 1);
    IF NOT fb.WorkOutput OR fb.Moving OR fb.AtWork OR fb.AtOrigin OR (fb.DoneToken <> 0) THEN w失败 := 5; END_IF;
    ui阶段 := 6;
6:
    fb(CancelMode := 0);
    IF fb.Moving OR fb.AtWork OR (fb.DoneToken <> 0) THEN w失败 := 6; END_IF;
    ui阶段 := 7;
7:
    fb(Execute := TRUE, Token := 4, Code := 42);
    IF fb.WorkOutput OR fb.OriginOutput OR (fb.DoneToken <> 0) THEN w失败 := 7; END_IF;
    fb原点(Execute := TRUE, Token := 1, Code := 41, HasWorkSensor := FALSE, HasOriginSensor := FALSE,
        DelayMs := 20, HomeDelayMs := 30, TimeoutMs := 500, ValveType := 0, HardEstop := FALSE, CancelMode := 0);
    IF NOT fb原点.Moving OR fb原点.WorkOutput OR fb原点.OriginOutput THEN w失败 := 8; END_IF;
    ui阶段 := 8;
8:
    fb原点(Execute := FALSE);
    IF fb原点.DoneToken = 1 THEN ui阶段 := 9; END_IF;
9:
    fb(Execute := TRUE, Token := 5, Code := 41, CancelMode := 0);
    ui阶段 := 10;
10:
    fb(Execute := FALSE, CancelMode := 1);
    IF fb.OriginOutput OR fb.Moving OR (fb.DoneToken <> 0) THEN w失败 := 9; END_IF;
    ui阶段 := 11;
11:
    fb(Execute := TRUE, Token := 6, Code := 40, CancelMode := 0, HasWorkSensor := TRUE,
        HasOriginSensor := TRUE, SensorWork := TRUE, SensorOrigin := FALSE);
    ui阶段 := 12;
12:
    (* 传感器跌落应重置连续确认延时。 *)
    fb(Execute := FALSE, SensorWork := FALSE);
    IF fb.AtWork OR (fb.DoneToken <> 0) THEN w失败 := 10; END_IF;
    ui阶段 := 13;
13:
    fb(SensorWork := TRUE);
    IF fb.DoneToken = 6 THEN ui阶段 := 14; END_IF;
14:
    fb(HardEstop := TRUE);
    IF NOT fb.Fault OR fb.WorkOutput OR fb.OriginOutput OR (fb.DoneToken <> 0) THEN w失败 := 11; END_IF;
    ui阶段 := 15;
15:
    fb(HardEstop := FALSE);
    IF NOT fb.Fault THEN w失败 := 12; END_IF;
    ui阶段 := 16;
16:
    fb(Execute := TRUE, Token := 7, Code := 42);
    IF fb.Fault OR fb.WorkOutput OR fb.OriginOutput OR (fb.DoneToken <> 0) THEN w失败 := 13; END_IF;
    ui阶段 := 17;
17:
    (* 释放动作未见原点：超时应立即关破真空，不能等待下扫描。 *)
    fb(Execute := TRUE, Token := 8, Code := 41, SensorWork := FALSE, SensorOrigin := FALSE,
        DelayMs := 0, HomeDelayMs := 0, TimeoutMs := 40);
    IF NOT fb.OriginOutput THEN w失败 := 14; END_IF;
    ui阶段 := 18;
18:
    fb(Execute := FALSE);
    IF fb.Fault THEN
        IF (fb.Error <> 2140) OR fb.OriginOutput OR fb.WorkOutput OR fb.Moving THEN w失败 := 15; END_IF;
        ui阶段 := 19;
    END_IF;
19:
    fb(Execute := TRUE, Token := 9, Code := 42);
    fb(Execute := TRUE, Token := 10, Code := 41);
    IF NOT fb.OriginOutput THEN w失败 := 16; END_IF;
    ui阶段 := 20;
20:
    (* 释放中的双传感器冲突同样关破真空。 *)
    fb(Execute := FALSE, SensorWork := TRUE, SensorOrigin := TRUE);
    IF NOT fb.Fault OR (fb.Error <> 2110) OR fb.OriginOutput THEN w失败 := 17; END_IF;
    ui阶段 := 21;
21:
    fb(Execute := TRUE, Token := 11, Code := 42, SensorWork := FALSE, SensorOrigin := FALSE);
    fb(Execute := TRUE, Token := 12, Code := 40);
    ui阶段 := 22;
22:
    (* 吸附超时保持原吸附输出，但绝不打开破真空。 *)
    fb(Execute := FALSE);
    IF fb.Fault THEN
        IF (fb.Error <> 2140) OR NOT fb.WorkOutput OR fb.OriginOutput THEN w失败 := 18; END_IF;
        ui阶段 := 23;
    END_IF;
23:
    (* 独立配置调用：DO0/DI0允许跨空间重号，同空间跨缸别名拒绝。 *)
    lw原绑定 := lw已绑定气缸;
    lw已绑定气缸 := 3;
    FOR i := 0 TO 1 DO
        st配置.aw气缸配置[i, 0] := 0;
        st配置.aw气缸配置[i, 1] := UINT_TO_WORD(i);
        st配置.aw气缸配置[i, 2] := WORD#16#FFFF;
        st配置.aw气缸配置[i, 3] := UINT_TO_WORD(1 - i);
        st配置.aw气缸配置[i, 4] := WORD#16#FFFF;
        st配置.aw气缸配置[i, 5] := 10;
        st配置.aw气缸配置[i, 6] := 100;
        st配置.aw气缸配置[i, 7] := 10;
    END_FOR;
    IF NOT 气缸_配置有效(缸号 := 0, Store := st配置) THEN w失败 := 19; END_IF;
    st配置.aw气缸配置[1, 1] := 0;
    IF 气缸_配置有效(缸号 := 0, Store := st配置) THEN w失败 := 20; END_IF;
    st配置.aw气缸配置[1, 1] := 1;
    st配置.aw气缸配置[1, 3] := 1;
    IF 气缸_配置有效(缸号 := 0, Store := st配置) THEN w失败 := 21; END_IF;
    lw已绑定气缸 := lw原绑定;
    ui阶段 := 24;
24:
    (* 隔离工程中检查真实调度器：手动待复位仍可受理且不被同扫描取消。
       自测不调用物理输出映射，正式工程不得挂此程序。 *)
    lw原绑定 := lw已绑定气缸;
    lw已绑定气缸 := 1;
    FOR i := 0 TO 7 DO
        全局变量_保持区.Store.aw气缸配置[0, i] := st配置.aw气缸配置[0, i];
    END_FOR;
    ab气缸映射有效[0] := TRUE;
    ab气缸模块就绪[0] := TRUE;
    ab气缸动点传感器[0] := FALSE;
    ab气缸原点传感器[0] := FALSE;
    st运行时.b手动 := TRUE;
    st运行时.bHMI在线 := TRUE;
    st运行时.b待复位 := TRUE;
    全局变量_气缸请求.ast请求[0].b自动 := FALSE;
    全局变量_气缸请求.ast请求[0].b待下发 := TRUE;
    全局变量_气缸请求.ast请求[0].b忙 := TRUE;
    全局变量_气缸请求.ast请求[0].udi请求号 := 1;
    全局变量_气缸请求.ast请求[0].w命令 := 40;
    fb调度(StopAll := FALSE, Runtime := st运行时);
    IF NOT ab气缸动点输出[0] OR NOT st运行时.ast气缸[0].b运动中
        OR NOT 全局变量_气缸请求.ast请求[0].b忙 THEN w失败 := 22; END_IF;
    (* 同样待复位条件下自动请求被撤销，不能沿用手动的输出完成资格。 *)
    st运行时.b手动 := FALSE;
    st运行时.b运行 := TRUE;
    全局变量_气缸请求.ast请求[0].b自动 := TRUE;
    全局变量_气缸请求.ast请求[0].b待下发 := TRUE;
    全局变量_气缸请求.ast请求[0].udi请求号 := 2;
    fb调度(StopAll := FALSE, Runtime := st运行时);
    IF st运行时.ast气缸[0].b运动中 OR 全局变量_气缸请求.ast请求[0].b忙 THEN w失败 := 23; END_IF;
    (* 真实语义API：取消覆盖忙槽并登记新令牌；被拒绝动作保留该令牌。 *)
    全局变量_气缸请求.ast请求[0].b忙 := TRUE;
    全局变量_气缸请求.ast请求[0].b待下发 := TRUE;
    IF NOT Cy取消(0) THEN w失败 := 24; END_IF;
    udi夹紧请求号 := Cy设备状态[0].udi请求号;
    IF (udi夹紧请求号 = 0)
        OR (udi夹紧请求号 <> 全局变量_气缸请求.ast请求[0].udi请求号)
        OR (全局变量_气缸请求.ast请求[0].w命令 <> 42) THEN w失败 := 25; END_IF;
    IF Cy动点(0) OR Cy原点(0) THEN w失败 := 26; END_IF;
    IF Cy设备状态[0].udi请求号 <> udi夹紧请求号 THEN w失败 := 27; END_IF;
    IF Cy取消(54) OR Cy动点(54) OR Cy原点(54) THEN w失败 := 28; END_IF;
    lw已绑定气缸 := lw原绑定;
    b完成 := TRUE;
END_CASE;
END_PROGRAM
