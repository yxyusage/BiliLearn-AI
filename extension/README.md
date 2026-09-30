# BiliLearn-AI Edge 浏览器插件

在 B 站看视频时一键生成 AI 结构化笔记，支持时间戳跳转、知识点浏览。

## 功能

- 🎬 自动识别当前 B 站视频
- ⚡ 一键生成 AI 结构化笔记
- 📑 章节目录浏览，点击时间戳直接跳转视频
- 📋 笔记摘要预览
- 🔗 一键打开完整笔记页面
- 🟢 后端连接状态实时显示

## 安装方法（开发者模式）

1. 打开 Edge 浏览器，地址栏输入 `edge://extensions/`
2. 开启左下角「开发人员模式」
3. 点击「加载解压缩的扩展」
4. 选择本项目的 `extension` 文件夹
5. 插件安装完成，工具栏会出现 BiliLearn-AI 图标

## 使用方法

1. 先启动 BiliLearn-AI 后端（运行项目根目录的 `start.bat`）
2. 打开任意 B 站视频页面
3. 点击工具栏的 BiliLearn-AI 插件图标
4. 点击「生成笔记」，等待 AI 生成
5. 生成完成后，点击章节标题即可跳转到视频对应时间点

## 注意事项

- 插件依赖本地后端服务，后端未启动时无法使用
- 仅在 B 站视频页面（`bilibili.com/video/`）生效
- 笔记数据存储在本地数据库，不会上传到任何服务器
- 生成笔记需要配置好 AI API Key（在后端设置页面配置）

## 文件结构

```
extension/
├── manifest.json          # 插件配置（MV3）
├── background.js          # 后台服务脚本，转发 API 请求
├── content/
│   ├── content.js         # 注入 B 站页面，获取视频信息+控制播放器
│   └── content.css        # 注入页面样式
├── popup/
│   ├── popup.html         # 弹窗界面
│   ├── popup.css          # 弹窗样式
│   └── popup.js           # 弹窗逻辑
├── icons/                 # 插件图标
└── README.md              # 本文件
```
