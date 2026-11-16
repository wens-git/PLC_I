FUNCTION Axis_MoveToPoint : BOOL
VAR_INPUT
    ui轴号 : UINT;
    ui槽号 : UINT;
END_VAR
Axis_MoveToPoint := Axis_提交(ui轴号 := ui轴号, w命令 := 29, ui槽号 := ui槽号);
END_FUNCTION
