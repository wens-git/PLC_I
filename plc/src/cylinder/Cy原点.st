(* 请求到原点/释放。TRUE=已登记。 *)
FUNCTION Cy原点 : BOOL
VAR_INPUT 设备 : UINT; END_VAR
Cy原点 := Cy提交(设备 := 设备, 命令 := 41);
END_FUNCTION
