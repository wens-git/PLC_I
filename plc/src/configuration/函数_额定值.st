FUNCTION 函数_额定值 : BOOL
VAR_INPUT
    AxisIndex : UINT;
    Field : UINT;
    Value : UDINT;
END_VAR
VAR
    udi最大值 : UDINT;
END_VAR
函数_额定值 := FALSE;
IF AxisIndex >= 16 THEN RETURN; END_IF;
CASE Field OF
    2, 3: udi最大值 := audi额定速度[AxisIndex];
    4: udi最大值 := audi额定加速度[AxisIndex];
    5: udi最大值 := audi额定减速度[AxisIndex];
    6: udi最大值 := audi额定停止减速度[AxisIndex];
ELSE RETURN;
END_CASE;
函数_额定值 := (udi最大值 > 0) AND (Value > 0)
    AND (Value <= udi最大值) AND (Value <= UDINT#2147483647);
END_FUNCTION
