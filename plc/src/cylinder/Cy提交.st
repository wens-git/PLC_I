(* 业务语义API共用的请求号登记；拒绝时保留最近一次已接受请求。
   底层气缸_提交仍是所有来源唯一入槽/许可入口。 *)
FUNCTION Cy提交 : BOOL
VAR_INPUT
    设备 : UINT;
    命令 : WORD;
END_VAR
VAR
    udi请求号 : UDINT;
END_VAR
Cy提交 := FALSE;
IF 设备 >= 54 THEN RETURN; END_IF;
udi请求号 := 气缸_提交(缸号 := 设备, 命令 := 命令, 自动 := TRUE,
    Runtime := 全局变量_气缸请求.st许可快照);
IF udi请求号 = 0 THEN RETURN; END_IF;
Cy设备状态[设备].udi请求号 := udi请求号;
Cy提交 := TRUE;
END_FUNCTION
