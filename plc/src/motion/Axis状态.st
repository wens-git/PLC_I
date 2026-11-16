(* 轴接口最近一次请求的状态。非法轴号按错误处理，与旧 Axis_Error 一致。 *)
FUNCTION Axis状态 : 结构体_Axis状态
VAR_INPUT 轴号 : UINT; END_VAR
Axis状态.b忙 := FALSE;
Axis状态.b完成 := FALSE;
Axis状态.b错误 := TRUE;
Axis状态.w错误码 := ERR_非法;
IF 轴号 >= 16 THEN RETURN; END_IF;
Axis状态.b忙 := 全局变量_轴请求.ast请求[轴号].b忙;
Axis状态.b完成 := 全局变量_轴请求.ast请求[轴号].b完成;
Axis状态.w错误码 := 全局变量_轴请求.ast请求[轴号].w错误;
Axis状态.b错误 := Axis状态.w错误码 <> ERR_已受理;
END_FUNCTION
