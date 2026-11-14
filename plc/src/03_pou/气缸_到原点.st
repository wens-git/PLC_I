FUNCTION 气缸_到原点 : UDINT
VAR_INPUT 缸号 : UINT; END_VAR
气缸_到原点 := 气缸_提交(缸号 := 缸号, 命令 := 41, 自动 := TRUE, Runtime := 全局变量_气缸请求.st许可快照);
END_FUNCTION
