(* 请求到动点/吸附。TRUE=已登记，内部保存请求号，业务无需自己持有。 *)
FUNCTION Cy动点 : BOOL
VAR_INPUT 设备 : UINT; END_VAR
Cy动点 := Cy提交(设备 := 设备, 命令 := 40);
END_FUNCTION
