(* 设备运行态：保存最近一次业务请求号，业务代码不需要自己保存令牌。 *)
TYPE 结构体_Cy设备 :
STRUCT
    udi请求号 : UDINT;
    w错误 : WORD;
END_STRUCT
END_TYPE
