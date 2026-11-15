(* 请求到动点/吸附。TRUE=已登记，内部保存请求号，业务无需自己持有。 *)
FUNCTION Cy动点 : BOOL
VAR_INPUT 设备 : UINT; END_VAR
Cy动点 := FALSE;
IF 设备 >= 54 THEN RETURN; END_IF;
IF 气缸_提交(缸号 := 设备, 命令 := 40, 自动 := TRUE,
    Runtime := 全局变量_气缸请求.st许可快照) = 0 THEN RETURN; END_IF;
Cy设备状态[设备].udi请求号 := 全局变量_气缸请求.ast请求[设备].udi请求号;
Cy动点 := TRUE;
END_FUNCTION
