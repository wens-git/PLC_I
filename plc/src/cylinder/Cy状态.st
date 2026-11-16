(* 设备最近一次请求的忙/完成/故障，令牌比对只在这里做一次。
   无请求返回故障 15；令牌失效（被其他来源替换）返回 19。 *)
FUNCTION Cy状态 : 结构体_Cy状态
VAR_INPUT 设备 : UINT; END_VAR
Cy状态.b忙 := FALSE;
Cy状态.b完成 := FALSE;
Cy状态.w故障 := ERR_非法;
IF 设备 >= 54 THEN
    RETURN;
END_IF;
IF Cy设备状态[设备].udi请求号 = 0 THEN
    RETURN;
END_IF;
Cy状态.w故障 := ERR_取消;
IF 全局变量_气缸请求.ast请求[设备].udi请求号 <> Cy设备状态[设备].udi请求号 THEN
    RETURN;
END_IF;
Cy状态.w故障 := 全局变量_气缸请求.ast请求[设备].w错误;
Cy状态.b忙 := 全局变量_气缸请求.ast请求[设备].b忙;
Cy状态.b完成 := (全局变量_气缸请求.ast请求[设备].udi完成号 = Cy设备状态[设备].udi请求号)
    AND NOT 全局变量_气缸请求.ast请求[设备].b忙;
END_FUNCTION
