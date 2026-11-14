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
    udi夹紧请求号 : UDINT; (* 业务示例：保存气缸_到动点(气缸编号.夹紧缸)返回值 *)
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
    b完成 := TRUE;
END_CASE;
END_PROGRAM
