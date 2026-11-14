(* 查询已受理请求的执行结果；提交返回0的拒绝须由调用者单独处理。 *)
FUNCTION 气缸_故障 : WORD
VAR_INPUT 缸号 : UINT; 请求号 : UDINT; END_VAR
气缸_故障 := 15;
IF (缸号 >= 54) OR (请求号 = 0) THEN RETURN; END_IF;
气缸_故障 := 19;
IF 全局变量_气缸请求.ast请求[缸号].udi请求号 <> 请求号 THEN RETURN; END_IF;
气缸_故障 := 全局变量_气缸请求.ast请求[缸号].w错误;
END_FUNCTION
