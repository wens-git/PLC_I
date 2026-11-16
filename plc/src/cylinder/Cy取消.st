(* 取消本次请求并撤销输出。TRUE=已登记；取消不代表到位。 *)
FUNCTION Cy取消 : BOOL
VAR_INPUT 设备 : UINT; END_VAR
Cy取消 := Cy提交(设备 := 设备, 命令 := 42);
END_FUNCTION
