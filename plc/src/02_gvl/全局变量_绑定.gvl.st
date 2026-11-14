(* Engineering binding, not proof of physical availability. *)
VAR_GLOBAL CONSTANT
    ui轴总数 : UINT := 16;
    ui气缸总数 : UINT := 54;
    ui点位池容量 : UINT := 120;
    w已绑定轴 : WORD := 16#0007;
    lw已绑定气缸 : LWORD := 全局变量_气缸工程.lw绑定;
    w绑定纪元 : WORD := 2;
    (* Slots 0/1/2: XJ_Axis0 / XJ_Axis1 / BusMotionAxis.
       Device-tree AXIS_REF_SM3 references must NOT be redeclared here.
       Slots 3..15 unbound; cylinder wiring unverified, all unbound.
       Do not replace unknown online/ready feedback with TRUE. *)
END_VAR
