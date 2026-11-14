FUNCTION 气缸_取消 : UDINT
VAR_INPUT 缸号 : UINT; END_VAR
气缸_取消 := 气缸_提交(缸号 := 缸号, 命令 := 42, 自动 := TRUE, Runtime := 全局变量_气缸请求.st许可快照);
END_FUNCTION
