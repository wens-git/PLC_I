(* Volatile per-cylinder consumer state published for bound slots; zeros stay
   published for unbound cylinders. Written by PRG consumers after the Server. *)
TYPE 结构体_气缸状态 :
STRUCT
    b在动点 : BOOL;
    b在原点 : BOOL;
    b运动中 : BOOL;
    b故障 : BOOL;
    w错误码 : WORD;
END_STRUCT
END_TYPE
