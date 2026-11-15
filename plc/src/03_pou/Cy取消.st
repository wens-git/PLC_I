(* 取消本次请求并撤销输出。TRUE=已登记；取消不代表到位。 *)
FUNCTION Cy取消 : BOOL
VAR_INPUT 设备 : UINT; END_VAR
Cy取消 := FALSE;
IF 设备 >= 54 THEN RETURN; END_IF;
IF 气缸_提交(缸号 := 设备, 命令 := 42, 自动 := TRUE,
    Runtime := 全局变量_气缸请求.st许可快照) = 0 THEN RETURN; END_IF;
Cy设备状态[设备].udi请求号 := 全局变量_气缸请求.ast请求[设备].udi请求号;
Cy取消 := TRUE;
END_FUNCTION
