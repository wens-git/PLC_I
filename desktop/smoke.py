"""Mock-only integration checks in the actual Qt WebEngine/QWebChannel runtime."""
import json
from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication


HELPERS = r"""
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const until = async (fn, label) => {
  for (let i=0; i<160; i++) { const value=fn(); if(value) return value; await sleep(50); }
  throw new Error('等待超时: '+label);
};
const button = (scope, text) => [...document.querySelectorAll(scope+' button')].find(e=>e.textContent.trim()===text);
const click = async (scope, text) => (await until(()=>button(scope,text),text)).click();
const nav = async path => { location.hash=path; await sleep(250); };
const emit = (phase, extra={}) => console.log('FM_SMOKE:'+JSON.stringify({phase,...extra}));
// Synthetic PointerEvents have no OS pointer to capture; real input retains the production capture path.
const press = () => {
  const target=document.querySelector('[aria-label="正向点动"]');
  const capture=target.setPointerCapture; target.setPointerCapture=()=>{};
  try { target.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,pointerId:7})); }
  finally { target.setPointerCapture=capture; }
};
"""


class DesktopSmoke(QObject):
    def __init__(self, window, report_path):
        super().__init__(window)
        self.window = window
        QApplication.instance().setQuitOnLastWindowClosed(False)
        self.report_path = Path(report_path)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.started = time.monotonic()
        self.report = {'passed': False, 'runtime': 'PySide6 QtWebEngine + QWebChannel', 'mode': 'mock only', 'checks': [], 'errors': []}
        self.stage = 'loading'
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.fail('桌面集成验证超时'))
        self.timer.start(90000)
        window.page.consoleMessage.connect(self.message)
        window.shutdownFinished.connect(self.finished)
        QTimer.singleShot(500, self.initial)

    def script(self, body):
        self.window.page.runJavaScript('(async()=>{' + HELPERS + body + "})().catch(error=>console.log('FM_SMOKE:'+JSON.stringify({phase:'error',message:String(error.stack||error)})))")

    def initial(self):
        self.stage = 'ui'
        self.script(r"""
await until(()=>document.querySelector('.offline-overlay'),'offline');
await until(()=>window.qt?.webChannelTransport,'Qt transport');
document.querySelector('.offline-overlay button').click();
await click('[role="dialog"]','模拟设备');
await click('[role="dialog"]','连接');
await until(()=>!document.querySelector('.offline-overlay'),'mock connect');
await nav('/axes/0');
await click('.page','使能');
await until(()=>document.body.textContent.includes('已使能'),'axis enable');
document.querySelector('[aria-label="修改轴名称"]').click();
let input=await until(()=>document.querySelector('[role="dialog"] input'),'name editor');
input.value='桌面验证轴'; input.dispatchEvent(new Event('input',{bubbles:true}));
await click('[role="dialog"]','保存名称');
await until(()=>!document.querySelector('[role="dialog"]'),'name saved');
await click('.page','轴参数');
input=await until(()=>document.querySelector('[aria-label="手动速度"]'),'axis config');
input.value='12.345'; input.dispatchEvent(new Event('input',{bubbles:true}));
await click('[role="dialog"]','提交并读回');
await until(()=>!document.querySelector('[role="dialog"]'),'config saved');
const select=document.querySelector('[aria-label="选择空闲点位槽"]');
select.value='16'; select.dispatchEvent(new Event('change',{bubbles:true}));
await click('.page','示教并认领');
await until(()=>document.querySelector('[aria-label="P16 位置"]'),'point teach');
for (let axis=0; axis<3; axis++) {
  await nav('/axes/'+axis);
  await click('.points-table tbody tr','示教');
  await until(()=>document.querySelector('.points-table tbody tr').textContent.includes('已示教'),'P0 taught');
  const enabled=document.querySelector('[aria-label="启用 P'+axis+'"]');
  if (!enabled.checked) enabled.click();
  await sleep(200);
}
await nav('/');
await click('.page','现场配置确认');
await until(()=>document.body.textContent.includes('现场配置已确认'),'configuration confirmed');
await click('body','复位');
await until(()=>!button('body','复位中'),'global reset settled');
await nav('/cylinders');
await until(()=>document.querySelector('.cylinder-table tbody tr button'),'cylinder view');
await click('.cylinder-table tbody tr','动点');
await until(()=>document.querySelector('.cylinder-table tbody tr td:nth-child(3) .badge')?.textContent.includes('动点 · 传感器确认'),'cylinder sensor confirmation');
document.querySelector('.cylinder-table tbody tr [title="气缸参数"]').click();
await until(()=>document.querySelector('[aria-label="原点确认延时"]'),'independent cylinder delay');
input=document.querySelector('[aria-label="原点确认延时"]');
input.value='450'; input.dispatchEvent(new Event('input',{bubbles:true}));
await click('[role="dialog"]','提交并读回');
await until(()=>!document.querySelector('[role="dialog"]'),'cylinder config saved');
await nav('/io');
await until(()=>document.querySelector('h1')?.textContent.includes('I/O'),'io view');
await nav('/diagnostics');
await until(()=>document.querySelector('h1')?.textContent.includes('诊断'),'diagnostics');
emit('ui');
await nav('/axes/0');
press();
emit('jog-minimize');
""")

    def message(self, value):
        if not value.startswith('FM_SMOKE:'):
            return
        packet = json.loads(value[len('FM_SMOKE:'):])
        phase = packet['phase']
        if phase == 'error':
            self.fail(packet['message'])
        elif phase == 'ui':
            state = self.window.bridge.service.state()
            try:
                assert state['mode'] == 'mock'
                assert state['axes'][0]['name'] == '桌面验证轴'
                assert state['axes'][0]['config']['manual_speed'] == 12.345
                assert state['points'][16]['owner'] == 0 and state['points'][16]['taught']
                assert state['cylinders'][0]['config']['home_delay_ms'] == 450
                self.report['checks'].append('cylinder sensor confirmation and independent home delay round trip')
                self.report['checks'] += ['offline startup', 'Qt transport available', 'UI mock connect', 'axis enable', 'name round trip', 'config round trip', 'point teach', 'cylinders / IO / diagnostics navigation']
                self.window.grab().save(str(self.report_path.with_suffix('.png')))
            except Exception as error:
                self.fail('界面操作读回不符: ' + repr(error))
        elif phase == 'jog-minimize':
            QTimer.singleShot(200, self.minimize)
        elif phase == 'jog-reload':
            QTimer.singleShot(200, self.reload)
        elif phase == 'jog-close':
            QTimer.singleShot(200, self.close_with_jog)

    def assert_jog(self):
        service = self.window.bridge.service
        assert service.host.worker is not None
        state = service.state()
        assert service.host.worker.jog is not None, repr({'error': '点动未启动', 'interactive': service.interactive,
            'active_window': self.window.isActiveWindow(), 'axis': state.get('axes', [None])[0], 'events': state.get('events', [])[-5:]})

    def minimize(self):
        try:
            self.assert_jog()
            self.window.showMinimized()
            QTimer.singleShot(300, self.restore)
        except Exception as error:
            self.fail(repr(error))

    def restore(self):
        try:
            assert self.window.bridge.service.host.worker.jog is None
            self.report['checks'].append('minimize revokes active jog')
            self.window.showNormal(); self.window.activateWindow(); self.window.raise_()
            self.script("await sleep(1000); await until(()=>document.hasFocus(),'window focus'); press(); emit('jog-reload');")
        except Exception as error:
            self.fail(repr(error))

    def reload(self):
        try:
            self.assert_jog()
            self.window.view.reload()
            QTimer.singleShot(1000, self.after_reload)
        except Exception as error:
            self.fail(repr(error))

    def after_reload(self):
        if self.window.bridge.service.host.worker.jog is not None:
            self.fail('页面重载没有撤销点动')
            return
        self.report['checks'].append('page reload revokes active jog')
        self.window.activateWindow()
        self.window.raise_()
        self.window.view.setFocus()
        self.script("await until(()=>!document.querySelector('.offline-overlay'),'reload reconnect'); await nav('/axes/0'); await until(()=>document.hasFocus(),'reload window focus'); await until(()=>document.querySelector('[aria-label=\"正向点动\"]'),'jog button'); press(); emit('jog-close');")

    def close_with_jog(self):
        try:
            self.assert_jog()
            self.worker = self.window.bridge.service.host.worker
            self.stage = 'closing'
            self.window.close()
        except Exception as error:
            self.fail(repr(error))

    def fail(self, error):
        if self.stage == 'failed':
            return
        self.report['errors'].append(str(error))
        self.stage = 'failed'
        self.save()
        self.window.close()

    def finished(self, error):
        self.timer.stop()
        if error:
            self.report['errors'].append(error)
        if self.stage == 'closing' and not error:
            if self.worker.thread.is_alive():
                self.report['errors'].append('通信线程未退出')
            else:
                self.report['checks'].append('close revokes jog and joins communication worker')
                self.report['passed'] = True
        self.save()
        QTimer.singleShot(0, lambda: QApplication.instance().exit(0 if self.report['passed'] else 2))

    def save(self):
        self.report['elapsed_seconds'] = round(time.monotonic() - self.started, 2)
        self.report_path.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
