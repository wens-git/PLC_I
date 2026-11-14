(* Isolated logic test: real API and server, synthetic axis feedback, no MC/IO. *)
PROGRAM 程序_轴接口自测
VAR
    Server : 功能块_服务端;
    Manager : 功能块_轴请求监视;
    Runtime : 结构体_运行时;
    Command : 类型_命令区;
    Published : 类型_发布区;
    Step : UINT;
    Passed : UDINT;
    Failed : UDINT;
    FirstFailure : UINT;
    Done : BOOL;
    Ok : BOOL;
    Check : BOOL;
    Result : BOOL;
    Sequence : WORD;
    Sequence1 : WORD;
    Wait : TON;
END_VAR

IF Done THEN RETURN; END_IF;
Check := TRUE;
Ok := TRUE;
CASE Step OF
    0:
        全局变量_保持区.Store.dw签名 := 0;
        Runtime.w轴消费掩码 := 7;
        Runtime.b运行 := TRUE;
        Runtime.b待复位 := FALSE;
        Runtime.ast轴[0].b在线 := TRUE;
        Runtime.ast轴[0].b已使能 := TRUE;
        Runtime.ast轴[0].b静止 := TRUE;
        Runtime.ast轴[0].b可下发 := TRUE;
        Command[0] := XJV1_SIGNATURE_HI;
        Command[1] := XJV1_SIGNATURE_LO;
        Command[2] := 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Runtime.b待复位 := FALSE;
        Result := Axis_MoveToPoint(0, 120);
        Ok := NOT Result AND Axis_Error(0) AND NOT Axis_Done(0);
    1:
        Result := Axis_MoveToPoint(0, 16);
        Ok := Result AND Axis_Busy(0) AND NOT Axis_Done(0);
        Result := Axis_Home(0);
        Ok := Ok AND NOT Result;
    2:
        (* Free slot must reject through the real shared dispatch path. *)
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := Axis_Error(0) AND NOT Axis_Done(0) AND (Runtime.aw轴命令[0] = 0);
    3:
        全局变量_保持区.Store.b已确认 := TRUE;
        全局变量_保持区.Store.aw点位[16, 0] := 0;
        全局变量_保持区.Store.aw点位[16, 1] := 1000;
        全局变量_保持区.Store.aw点位[16, 2] := 0;
        全局变量_保持区.Store.aw点位[16, 3] := 1000;
        全局变量_保持区.Store.aw点位[16, 4] := 3;
        Runtime.ast轴[0].w运动结果 := 2;
        Runtime.ast轴[0].w序列 := 65535;
        Result := Axis_MoveToPoint(0, 16);
        Ok := Result AND NOT Axis_Done(0);
    4:
        Runtime.b待复位 := FALSE;
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Sequence := Runtime.aw轴序列[0];
        Manager(Runtime := Runtime);
        Ok := (Runtime.aw轴命令[0] = 27) AND (Sequence <> 65535)
            AND (Runtime.adi轴目标[0] = 1000) AND NOT Axis_Done(0);
    5:
        Runtime.aw轴命令[0] := 0;
        Runtime.ast轴[0].w序列 := Sequence;
        Runtime.ast轴[0].w运动结果 := 1;
        Runtime.ast轴[0].b运动中 := TRUE;
        Runtime.ast轴[0].b静止 := FALSE;
        Manager(Runtime := Runtime);
        Ok := Axis_Busy(0) AND NOT Axis_Done(0);
    6:
        Runtime.ast轴[0].w运动结果 := 2;
        Runtime.ast轴[0].b运动中 := FALSE;
        Runtime.ast轴[0].b静止 := TRUE;
        Manager(Runtime := Runtime);
        Ok := Axis_Done(0) AND NOT Axis_Busy(0) AND NOT Axis_Error(0);
    7:
        Result := Axis_MoveToPoint(0, 16);
        Ok := Result AND NOT Axis_Done(0);
        Result := Axis_Stop(0);
        Ok := Ok AND Result AND NOT Axis_Done(0) AND Axis_Error(0);
    8:
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Manager(Runtime := Runtime);
        Ok := (Runtime.aw轴命令[0] = 26) AND NOT Axis_Done(0);
    9:
        Result := Axis_Home(0);
        Runtime.b运行 := FALSE;
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := Axis_Error(0) AND (Runtime.aw轴命令[0] = 0);
    10:
        Ok := NOT Axis_MoveToPoint(16, 0) AND NOT Axis_Done(16)
            AND Axis_Error(16) AND NOT Axis_Busy(16);
    11:
        Runtime.b运行 := TRUE;
        Runtime.ast轴[1].b在线 := TRUE;
        Runtime.ast轴[1].b已使能 := TRUE;
        Runtime.ast轴[1].b静止 := TRUE;
        Runtime.ast轴[1].b可下发 := TRUE;
        Result := Axis_Home(0);
        Ok := Result;
        Result := Axis_Home(1);
        Ok := Ok AND Result AND Axis_Busy(0) AND Axis_Busy(1);
    12:
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Sequence := Runtime.aw轴序列[0];
        Sequence1 := Runtime.aw轴序列[1];
        Ok := (Runtime.aw轴命令[0] = 22) AND (Runtime.aw轴命令[1] = 22);
    13:
        Runtime.ast轴[0].w序列 := Sequence;
        Runtime.ast轴[1].w序列 := Sequence1;
        Runtime.ast轴[0].w运动结果 := 1;
        Runtime.ast轴[1].w运动结果 := 1;
        Manager(Runtime := Runtime);
        Ok := Axis_Busy(0) AND Axis_Busy(1) AND NOT Axis_Done(0) AND NOT Axis_Done(1);
    14:
        Runtime.b暂停 := TRUE;
        Manager(Runtime := Runtime);
        Ok := Axis_Error(0) AND Axis_Error(1) AND NOT Axis_Done(0) AND NOT Axis_Done(1);
    15:
        Runtime.b暂停 := FALSE;
        Result := Axis_MoveToPoint(0, 16);
        Ok := Result;
        Command[3] := 26;
        Command[4] := 77;
        Command[5] := 16#0100;
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := Ok AND (Runtime.aw轴命令[0] = 26) AND Axis_Error(0) AND NOT Axis_Done(0);
    16:
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := (Runtime.aw轴命令[0] = 0) AND NOT Axis_Busy(0);
    17:
        Result := Axis_MoveToPoint(0, 16);
        Runtime.b暂停 := TRUE;
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := Result AND Axis_Error(0) AND (Runtime.aw轴命令[0] = 0);
    18:
        Runtime.b暂停 := FALSE;
        Runtime.b待复位 := TRUE;
        Result := Axis_Home(0);
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        Ok := Result AND Axis_Error(0) AND (Runtime.aw轴命令[0] = 0);
    19:
        (* Internal rejections must not replace the last network ACK. *)
        (* Wait past the 300ms publication period before checking network ACK. *)
        Wait(IN := TRUE, PT := T#400ms);
        Command[2] := Command[2] + 1;
        Server(Command := Command, Published := Published, Runtime := Runtime);
        IF NOT Wait.Q THEN Check := FALSE; RETURN; END_IF;
        Ok := (Published[3] = 77) AND (Published[4] = 0)
            AND (Published[5] = 16#0100) AND (Published[6] = 1);
        Done := TRUE;
END_CASE;
IF Check THEN
    IF Ok THEN Passed := Passed + 1;
    ELSE
        Failed := Failed + 1;
        IF FirstFailure = 0 THEN FirstFailure := Step + 1; END_IF;
    END_IF;
END_IF;
Step := Step + 1;
END_PROGRAM
