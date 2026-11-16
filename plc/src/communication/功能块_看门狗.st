FUNCTION_BLOCK 功能块_看门狗
VAR_INPUT
    SignatureOK : BOOL;
    Heartbeat : WORD;
    LeaseCounter : WORD;
    LeaseObject : WORD;
    LeaseSequence : WORD;
    StartJog : BOOL;
    StartObject : WORD;
    StartSequence : WORD;
    StopJog : BOOL;
END_VAR
VAR_OUTPUT
    Online : BOOL;
    ConnectedEdge : BOOL;
    CancelJog : BOOL;
    JogActive : BOOL;
    JogObject : WORD;
    JogSequence : WORD;
END_VAR
VAR
    b已初始化 : BOOL;
    w上次心跳 : WORD;
    w上次租约计数 : WORD;
    b心跳变化 : BOOL;
    b续租点动 : BOOL;
    tmr在线 : TON;
    tmr点动 : TON;
END_VAR

CancelJog := FALSE;
ConnectedEdge := FALSE;
IF NOT b已初始化 THEN
    w上次心跳 := Heartbeat;
    w上次租约计数 := LeaseCounter;
    b已初始化 := TRUE;
END_IF;
b心跳变化 := SignatureOK AND (Heartbeat <> w上次心跳);
w上次心跳 := Heartbeat;
tmr在线(IN := SignatureOK AND NOT b心跳变化, PT := T#1500ms);
IF NOT SignatureOK OR tmr在线.Q THEN
    Online := FALSE;
ELSIF b心跳变化 THEN
    ConnectedEdge := NOT Online;
    Online := TRUE;
END_IF;

b续租点动 := FALSE;
(* The lease is established unconditionally on the start pulse: an online flip
   between acceptance and this scan must not orphan an already-started jog.
   The cancel block below revokes it in the same scan when offline. *)
IF StartJog THEN
    JogActive := TRUE;
    JogObject := StartObject;
    JogSequence := StartSequence;
    w上次租约计数 := LeaseCounter;
    b续租点动 := TRUE;
ELSIF JogActive AND Online
AND (LeaseObject = JogObject)
AND (LeaseSequence = JogSequence)
AND (LeaseCounter <> w上次租约计数) THEN
    w上次租约计数 := LeaseCounter;
    b续租点动 := TRUE;
END_IF;
(* Connection heartbeat does not appear in the lease renewal expression. *)
tmr点动(IN := JogActive AND NOT b续租点动, PT := T#1500ms);
IF JogActive AND (StopJog OR NOT Online OR tmr点动.Q) THEN
    CancelJog := TRUE;
    JogActive := FALSE;
    JogSequence := 0;
END_IF;
END_FUNCTION_BLOCK
