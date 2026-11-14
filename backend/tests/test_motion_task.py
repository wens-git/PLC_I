"""Offline task migration behavior; not physical timing acceptance."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load_helper():
    path = Path(__file__).resolve().parents[2] / "plc/tools/motion_task.py"
    spec = importlib.util.spec_from_file_location("motion_task", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Node:
    def __init__(self, name, children=(), connectors=()):
        self.name = name
        self.children = list(children)
        self.connectors = list(connectors)
        for child in self.children:
            child.parent = self

    def get_name(self):
        return self.name

    def get_children(self, recursive=False):
        result = list(self.children)
        if recursive:
            for child in self.children:
                result.extend(child.get_children(True))
        return result

    def move(self, parent, index):
        self.parent.children.remove(self)
        parent.children.append(self)
        self.parent = parent

    def remove(self):
        self.parent.children.remove(self)


def test_task_migration_is_single_owner_idempotent_and_removes_empty_task():
    call = Node("PLC_PRG")
    main = Node("MainTask", [call])
    motion = Node("EtherCAT_Task")
    info = SimpleNamespace(bus_cycle_task_by_name="MainTask")
    info.set_bus_cycle_task = lambda name: setattr(info, "bus_cycle_task_by_name", name)
    device = Node("Ethernet", connectors=[SimpleNamespace(driver_info=info)])
    project = Node("project", [main, motion, device])
    helper = load_helper()
    helper.configure_motion_task(project, lambda text: None)
    helper.configure_motion_task(project, lambda text: None)
    assert main.children == []
    assert motion.children == [call]
    assert info.bus_cycle_task_by_name == "EtherCAT_Task"
    assert main not in project.children
    assert motion in project.children


def test_missing_bus_task_fails_before_any_mutation():
    import pytest
    call = Node("PLC_PRG")
    main = Node("MainTask", [call])
    with pytest.raises(RuntimeError):
        load_helper().configure_motion_task(Node("project", [main]), lambda text: None)
    assert main.children == [call]
