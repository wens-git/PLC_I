"""Single motion owner shared by offline importers (CPython/IronPython)."""


def configure_motion_task(project, emit):
    objects = list(project.get_children(True))
    tasks = [obj for obj in objects if obj.get_name() == "EtherCAT_Task"]
    if len(tasks) != 1:
        raise RuntimeError("Expected exactly one EtherCAT_Task")
    target = tasks[0]
    owners = []
    for obj in objects:
        if obj.get_name() in ("MainTask", "EtherCAT_Task"):
            owners.extend((obj, child) for child in obj.get_children(False)
                          if child.get_name() == "PLC_PRG")
    if len(owners) != 1:
        raise RuntimeError("Expected exactly one PLC_PRG task call")
    owner, call = owners[0]
    if owner.get_name() != target.get_name():
        call.move(target, -1)
    for obj in project.get_children(True):
        if obj.get_name() not in ("EtherCAT", "Ethernet", "ModbusTCP_Slave_XJV1", "HIGH_SPEED_IO"):
            continue
        for connector in obj.connectors:
            info = connector.driver_info
            info.set_bus_cycle_task("EtherCAT_Task")
            if info.bus_cycle_task_by_name != "EtherCAT_Task":
                raise RuntimeError("Failed to bind " + obj.get_name() + " to motion task")
    for obj in project.get_children(True):
        if obj.get_name() == "MainTask" and not list(obj.get_children(False)):
            obj.remove()
    emit("MOTION TASK VERIFIED owner=EtherCAT_Task calls=1 PLC_PRG")
