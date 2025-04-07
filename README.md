# IPTV-API

一个可高度自定义的IPTV接口更新项目📺，自定义频道菜单，自动获取直播源，测速验效后生成可用的结果，可实现『✨秒播级体验🚀』

## 特点
- ✅ 自定义模板，生成您想要的频道
- ✅ 支持RTMP推流(live/hls)，提升播放体验
- ✅ 支持多种获取源方式：本地源、组播源、酒店源、订阅源、关键字搜索
- ✅ 接口测速验效，获取延迟、速率、分辨率，过滤无效接口
- ✅ 偏好设置：IPv4、IPv6、接口来源排序优先级与数量配置、接口白名单
- ✅ 定时执行，北京时间每日 6:00 与 18:00 执行更新
- ✅ 支持多种运行方式：工作流、命令行、GUI 软件、Docker(amd64/arm64/arm v7)
- ✨ 更多功能请见[配置参数](#配置)

## 快速上手
### 工作流部署
1. 进入IPTV-API项目，打开 https://github.com/Guovin/iptv-api 点击`Star`收藏该项目。
2. 修改配置：
   - 订阅源（`config/subscribe.txt`）：支持txt和m3u地址作为订阅，程序将依次读取其中的频道接口数据。
   - 本地源（`config/local.txt`）：频道接口数据来源于本地文件，程序将依次读取其中的频道接口数据。
   - 黑名单（`config/blacklist.txt`）：符合黑名单关键字的接口将会被过滤，不会被收集。
   - 白名单（`config/whitelist.txt`）：白名单内的接口或订阅源获取的接口将不会参与测速，优先排序至结果最前。
   - 组播数据（`config/rtp`）：对于组播源数据你也可以自行维护，文件位于config/rtp目录下，文件命名格式为：`地区_运营商.txt`。
3. 运行更新工作流：
   - 首次执行工作流需要您手动触发，后续执行（默认北京时间`每日6:00与18:00`）将自动触发。如果您修改了模板或配置文件想立刻执行更新，可手动触发`Run workflow`。
   - 如果一切正常，稍等片刻后就可以看到该条工作流已经执行成功（绿色勾图标）。
   - 此时您可以访问文件链接，查看最新结果有没有同步即可：
     - https://raw.githubusercontent.com/您的github用户名/仓库名称（对应上述Fork创建时的iptv-api）/master/output/user_result.txt
     - 或者代理地址：https://cdn.jsdelivr.net/gh/您的github用户名/仓库名称（对应上述Fork创建时的TV）@master/output/user_result.txt
   - 如果访问该链接能正常返回更新后的接口内容，说明您的直播源接口链接已经大功告成了！将该链接复制粘贴到`TVBox`等播放器配置栏中即可使用。

### GUI 软件
1. 下载[IPTV-API 更新软件](https://github.com/Guovin/iptv-api/releases)，打开软件，点击更新，即可完成更新。
2. 或者在项目目录下运行以下命令，即可打开 GUI 软件：
```shell
pipenv run ui