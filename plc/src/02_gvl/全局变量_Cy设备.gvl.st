(* 设备编号：业务代码用名称表达设备，不用记数字。
   名称与现场绑定无关；未绑定设备调用动作会被拒绝。 *)
VAR_GLOBAL CONSTANT
    Cy夹紧 : UINT := 0;
    Cy定位 : UINT := 1;
END_VAR
VAR_GLOBAL
    (* 每个设备保存最近一次请求号，业务不需要自己管理令牌。 *)
    Cy设备状态 : ARRAY[0..53] OF 结构体_Cy设备;
END_VAR
