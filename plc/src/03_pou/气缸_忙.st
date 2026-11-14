FUNCTION 气缸_忙 : BOOL
VAR_INPUT 缸号 : UINT; 请求号 : UDINT; END_VAR
气缸_忙 := FALSE;
IF (缸号 >= 54) OR (请求号 = 0) THEN RETURN; END_IF;
气缸_忙 := (全局变量_气缸请求.ast请求[缸号].udi请求号 = 请求号)
    AND 全局变量_气缸请求.ast请求[缸号].b忙;
END_FUNCTION
