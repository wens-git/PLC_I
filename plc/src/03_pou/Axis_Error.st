FUNCTION Axis_Error : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR

Axis_Error := TRUE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
Axis_Error := 全局变量_轴请求.ast请求[ui轴号].w错误 <> 0;
END_FUNCTION
