TYPE 结构体_轴状态 :
STRUCT
    b在线 : BOOL;
    b已使能 : BOOL;
    b运动中 : BOOL;
    b已回原 : BOOL;
    b故障 : BOOL;
    b静止 : BOOL;
    b可下发 : BOOL;
    b正向点动 : BOOL;
    b负向点动 : BOOL;
    di位置 : DINT;
    di速度 : DINT;
    di目标 : DINT;
    w错误码 : WORD;
    dw驱动错误 : DWORD;
    w序列 : WORD;
    w运动结果 : WORD;
    w限位 : WORD;
END_STRUCT
END_TYPE
