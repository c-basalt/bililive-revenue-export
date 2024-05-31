# B站直播礼物流水导出

从个人账号直播数据的[直播收益](https://link.bilibili.com/p/center/index#/live-data/gift-list)页面按天导出完整的礼物/道具记录

## 功能和特性

- 随时从自己账号的直播收益页面导出数据，无需时刻开启软件
- 支持从本地的主流浏览器（非隐身模式）自动提取登录信息，无需手动登录
- 历史日期数据成功获取后保存在本地的raw文件夹下，raw文件夹内存在数据则后续不再重复获取
- 导出数据按UID-日期以excel格式保存在table文件夹内，每次导出会覆盖已有文件

## 局限

- 仅能导出自己账号的数据，仅能导出直播收益页面中包含的数据，较弹幕姬类别工具能获取的内容更少
- 只能获取最近半年内的数据
- 仅原样导出数据，没有过滤、合并、数据分析等

## 使用

- 下载安装Python3：https://www.python.org/downloads/
- 下载解压源代码：https://github.com/c-basalt/bililive-revenue-export/archive/refs/heads/main.zip
- 双击运行run.bat
