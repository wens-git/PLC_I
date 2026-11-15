VAR_GLOBAL CONSTANT
    (* Protocol milli-units. These are provisional caps for bench bring-up:
       edit per drive/mechanics rating and re-download. 0 would block every
       parameter write, so never publish an all-zero array. *)
    audi额定速度 : ARRAY[0..15] OF UDINT := [16(1000000)];      (* 1000 mm/s *)
    audi额定加速度 : ARRAY[0..15] OF UDINT := [16(10000000)];   (* 10000 mm/s² *)
    audi额定减速度 : ARRAY[0..15] OF UDINT := [16(10000000)];
    audi额定停止减速度 : ARRAY[0..15] OF UDINT := [16(20000000)];
END_VAR
VAR_GLOBAL
    (* Pulse axes have no external Ready input. Their availability is derived
       from MC feedback; it does not prove that a pulse drive has power. *)
    ab正限位 : ARRAY[0..2] OF BOOL;
    ab负限位 : ARRAY[0..2] OF BOOL;
    (* Cylinder commissioning seam. Sensor inputs default FALSE until the IO image
       is mapped; valve demands are written to 全局变量_气缸IO映像 by the output map. *)
    ab气缸模块就绪 : ARRAY[0..53] OF BOOL; (* 由真实模块在线位推导，不可手工赋值 *)
    ab气缸映射有效 : ARRAY[0..53] OF BOOL; (* 由绑定、配置有效和地址容量推导 *)
    ab气缸动点传感器 : ARRAY[0..53] OF BOOL;
    ab气缸原点传感器 : ARRAY[0..53] OF BOOL;
    ab气缸动点输出 : ARRAY[0..53] OF BOOL;
    ab气缸原点输出 : ARRAY[0..53] OF BOOL;
END_VAR
