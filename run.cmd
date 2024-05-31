IF NOT EXIST .venv py.exe -m venv .venv
IF NOT EXIST .venv\Lib\site-packages\aiohttp .venv\Scripts\pip.exe install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
.venv\Scripts\python.exe main.py
