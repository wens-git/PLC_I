TYPE 结构体_轴请求 :
STRUCT
    w命令 : WORD;
    ui槽号 : UINT;
    w序列 : WORD;
    w错误 : WORD;
    b忙 : BOOL;
    b已下发 : BOOL;
    b已接收 : BOOL;
    b完成 : BOOL;
END_STRUCT
END_TYPE
