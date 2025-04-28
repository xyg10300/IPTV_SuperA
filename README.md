![IPTV](https://socialify.git.ci/alantang1977/IPTV_SuperA/image?description=1&descriptionEditable=IPTV%20%E7%9B%B4%E6%92%AD%E6%BA%90&forks=1&language=1&name=1&owner=1&pattern=Circuit%20Board&stargazers=1&theme=Auto)

# IPTV-API

一个可高度自定义的IPTV接口更新项目📺，自定义频道菜单，自动获取直播源，测速验效后生成可用的结果，可实现『✨秒播级体验🚀』

## 快速上手
### 工作流部署
1. 进入IPTV-API项目，打开 https://github.com/alantang1977/IPTV_SuperA 点击`Star`收藏该项目。
2. 修改配置：
   - 订阅源（`config/subscribe.txt`）：支持txt和m3u地址作为订阅，程序将依次读取其中的频道接口数据。
3. 运行更新工作流：
   - 首次执行工作流需要您手动触发，后续执行（默认北京时间`每日6:00与18:00`）将自动触发。如果您修改了模板或配置文件想立刻执行更新，可手动触发`Run workflow`。
   - 如果一切正常，稍等片刻后就可以看到该条工作流已经执行成功（绿色勾图标）。
   - 此时您可以访问文件链接，查看最新结果有没有同步即可：
     - https://raw.githubusercontent.com/您的github用户名/仓库名称（对应上述Fork创建时的IPTV_SuperA）/master/output/result.m3u
     - 或者代理地址：https://cdn.jsdelivr.net/gh/您的github用户名/仓库名称（对应上述Fork创建时的TV）@master/output/result.txt
   - 如果访问该链接能正常返回更新后的接口内容，说明您的直播源接口链接已经大功告成了！将该链接复制粘贴到`TVBox`等播放器配置栏中即可使用。
