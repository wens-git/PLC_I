(* 已通过协议/候选flags校验的点位：16为空槽，其余为轴0..15。
   空槽必须精确等于FREE，轴15不会与空槽混淆。 *)
FUNCTION 函数_点位归属 : INT
VAR_INPUT
    Flags : WORD;
END_VAR
IF Flags = XJV1_POINT_FREE THEN
    函数_点位归属 := 16;
ELSE
    函数_点位归属 := WORD_TO_INT(SHR(Flags, 2) AND WORD#16#000F);
END_IF;
END_FUNCTION
