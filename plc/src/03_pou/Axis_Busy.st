FUNCTION Axis_Busy : BOOL
VAR_INPUT
    ui轴号 : UINT;
END_VAR

Axis_Busy := FALSE;
IF ui轴号 >= 16 THEN RETURN; END_IF;
Axis_Busy := 全局变量_轴请求.ast请求[ui轴号].b忙;
END_FUNCTION
