import sys
import json
import traceback
import asyncio
import threading

from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QWidget,
)
from PySide6.QtGui import (
    QIntValidator,
)
from PySide6.QtCore import (
    QDate,
    Signal,
)

from rookiepy import (
    chrome,
    firefox,
    chromium,
    edge,
    vivaldi,
    opera,
    brave,
)
import requests
import aiohttp

from revenue_dump import Dumper


browsers = {
    'Chrome': chrome,
    'Firefox': firefox,
    'Chromium': chromium,
    'Edge': edge,
    'Vivaldi': vivaldi,
    'Opera': opera,
    'Brave': brave,
}


class Config:
    _CONFIG_FILE = 'config.json'

    def __init__(self):
        try:
            with open(self._CONFIG_FILE, 'rt') as f:
                self._config = json.load(f)
        except Exception:
            self._config = {}

    def set(self, key, value):
        self._config[key] = value
        try:
            with open(self._CONFIG_FILE, 'wt') as f:
                json.dump(self._config, f, indent=4)
        except Exception:
            traceback.print_exc()

    def get(self, key, default):
        value = self._config.get(key, default)
        return value if isinstance(value, type(default)) else default


class CookieDialog(QDialog):
    def __init__(self, update_cookies):
        super().__init__()
        self.update_cookies = update_cookies

        self.setWindowTitle('请选择B站账号')
        self._layout = QVBoxLayout()

        self.message_label = QLabel('请从常见浏览器中选择要用于导出的主播账号，或者手动输入cookie string')
        self._layout.addWidget(self.message_label)

        for label in browsers:
            self._layout.addWidget(self.get_cookie_btn(label))

        cookie_str_hint = QLabel('手动从浏览器使用F12复制cookie string到下面（<a href="https://www.bilibili.com/read/cv26807223/" rel=noreferrer>教程</a>）')
        cookie_str_hint.setOpenExternalLinks(True)
        self._layout.addWidget(cookie_str_hint)
        self.cookie_str_box = QLineEdit(self)
        self._layout.addWidget(self.cookie_str_box)
        cookie_str_btn = QPushButton('使用cookie string', self)
        cookie_str_btn.clicked.connect(lambda _: self.extract_cookie_str())
        self._layout.addWidget(cookie_str_btn)

        self.setLayout(self._layout)

    def set_cookies(self, uid, uname, cookies, source):
        self.message_label.setText(f'已选择：{uname} ({uid}) {source}')
        self.update_cookies(uid, uname, cookies, source)

    def validate_cookie(self, cookies, source):
        if not cookies.get('SESSDATA'):
            raise ValueError('无可用B站账号cookie')
        r_json = requests.get('https://api.bilibili.com/x/web-interface/nav', headers={
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }, cookies=cookies, timeout=10).json()
        if r_json['code'] != 0:
            raise ValueError(f'cookie无效或已过期\n{r_json}')
        self.set_cookies(r_json['data']['mid'], r_json['data']['uname'], cookies, source)

    def extract_browser_cookie(self, label: str, silent=False):
        try:
            cookie_list = browsers[label](domains=['bilibili.com'])
            cookies = {item['name']: item['value'] for item in cookie_list}
            self.validate_cookie(cookies, label)
        except Exception as e:
            if not silent:
                if str(e).startswith("can't find cookies file"):
                    QMessageBox.warning(self, 'cookie提取失败', f'未找到该浏览器的cookie文件\n\n{traceback.format_exc()}')
                else:
                    QMessageBox.warning(self, 'cookie无效', f'cookie检测失败\n\n{traceback.format_exc()}')

    def extract_cookie_str(self):
        try:
            cookie_str = self.cookie_str_box.text()
            cookies = {k.strip(): v.strip() for k, v in (i.split('=') for i in cookie_str.split(';'))}
            self.validate_cookie(cookies, '')
        except Exception:
            QMessageBox.warning(self, 'cookie无效', f'cookie string检测失败\n\n{traceback.format_exc()}')

    def get_cookie_btn(self, label: str):
        def _extract(_):
            return self.extract_browser_cookie(label)

        button = QPushButton(label, self)
        button.clicked.connect(_extract)
        return button


class MainWindow(QMainWindow):
    export_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.cookies = {}
        self.uid = 0
        self.uname = ''

        self.setWindowTitle('B站直播礼物数据导出')

        self._layout = QVBoxLayout()

        msg_hint = QLabel('从直播数据的“<a href="https://link.bilibili.com/p/center/index#/live-data/gift-list">直播收益</a>”导出对应日期的礼物记录')
        msg_hint.setOpenExternalLinks(True)
        self._layout.addWidget(msg_hint)

        self._layout.addLayout(self._get_account_layout())
        self._layout.addLayout(self._get_dump_control_layout())

        main_widget = QWidget()
        main_widget.setLayout(self._layout)
        self.setCentralWidget(main_widget)

        self.auto_load_cookies()

    def _get_account_layout(self):
        layout = QHBoxLayout()

        self.account_msg = QLabel('当前未选择B站账号')
        layout.addWidget(self.account_msg)

        cookie_button = QPushButton('选择B站账号')
        cookie_button.clicked.connect(self.raise_cookie_dialog)
        layout.addWidget(cookie_button)

        return layout

    def _get_dump_control_layout(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel('导出最晚日期'))
        self.begin_date_input = QDateEdit(QDate.currentDate())
        layout.addWidget(self.begin_date_input)

        layout.addWidget(QLabel('导出天数'))
        self.num_days_input = QLineEdit('10')
        self.num_days_input.setValidator(QIntValidator(1, 180))
        layout.addWidget(self.num_days_input)

        self.start_button = QPushButton('开始导出')
        self.start_button.clicked.connect(self.start_dump)
        layout.addWidget(self.start_button)

        self.export_signal.connect(self._pop_warn)

        return layout

    def _pop_warn(self, s):
        QMessageBox.warning(self, '流水导出出错', f'导出时遇到错误\n\n{s}')

    def start_dump(self):
        async def _dump(dt, n):
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                dumper = Dumper(self.cookies, session=s)
                await dumper.dump_date_range(dt, n)

        def _dump_worker():
            try:
                self.start_button.setEnabled(False)
                self.start_button.setText('正在导出……')
                n = int(self.num_days_input.text())
                dt = self.begin_date_input.dateTime().toPython()
                asyncio.run(_dump(dt, n))
            except Exception:
                traceback.print_exc()
                self.export_signal.emit(traceback.format_exc())
            finally:
                self.start_button.setText('开始导出')
                self.start_button.setEnabled(True)

        if not self.cookies:
            return self.raise_cookie_dialog(None)

        t = threading.Thread(target=_dump_worker)
        t.start()

    def update_cookies(self, uid, uname, cookies, source):
        self.config.set('uid', uid)
        self.config.set('cookie_src', source)
        self.uid = uid
        self.uname = uname
        self.cookies = cookies
        self.account_msg.setText(f'当前B站账号：{self.uname} ({self.uid})')

    def raise_cookie_dialog(self, _):
        CookieDialog(self.update_cookies).exec()

    def auto_load_cookies(self):
        if self.config.get('uid', 0) and self.config.get('cookie_src', ''):
            def _update(uid, uname, cookies, source):
                if uid == self.config.get('uid', 0):
                    self.update_cookies(uid, uname, cookies, source)
            dialog = CookieDialog(_update)
            dialog.extract_browser_cookie(self.config.get('cookie_src', ''), silent=True)
        if not self.cookies:
            self.raise_cookie_dialog(None)


app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()
