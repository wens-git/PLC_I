"""Architecture ownership boundaries, independent of source file counts."""
from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[2] / 'plc/src'

def text(domain, name):
    return (ROOT / domain / (name + '.st')).read_text(encoding='utf-8')

def test_main_is_ordered_composition_and_mc_has_one_owner():
    main = text('entry', '程序_主循环')
    calls = ['程序_气缸绑定();', 'fb服务端(', 'fb模式(', 'fb轴组(', '程序_气缸输入映射();', 'fb气缸调度(', '程序_气缸输出映射();']
    positions = [main.index(call) for call in calls]
    assert positions == sorted(positions)
    assert len(main.splitlines()) < 50
    assert 'MC_' not in main
    group = text('motion', '功能块_轴组')
    for axis in range(3):
        assert len(re.findall(rf'fb轴{axis}\(', group)) == 1
    owners = [p for p in ROOT.rglob('*.st') if ': MC_MoveAbsolute;' in p.read_text(encoding='utf-8')]
    assert [p.name for p in owners] == ['功能块_轴.st']

def test_published_image_has_one_owner_and_no_runtime_cache():
    writers = [p.name for p in ROOT.rglob('*.st') if re.search(r'Published\[[^\n]+:=', p.read_text(encoding='utf-8'))]
    assert writers == ['功能块_状态发布.st']
    server = text('communication', '功能块_服务端')
    assert len(server.splitlines()) < 350
    assert '结构体_运行时' not in re.search(r'(?m)^VAR\n(.*?)END_VAR', server, re.S)[1]
    assert not list(ROOT.rglob('结构体_气缸工程.st'))
