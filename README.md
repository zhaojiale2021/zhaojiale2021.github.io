# zhaojiale2021.github.io

[![CI](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/ci.yml/badge.svg)](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/ci.yml)
[![同步仓库缓存](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/sync-repos.yml/badge.svg)](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/sync-repos.yml)
[![Lighthouse](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/lighthouse.yml/badge.svg)](https://github.com/zhaojiale2021/zhaojiale2021.github.io/actions/workflows/lighthouse.yml)

Alan Zhao 的个人主页 —— 嵌入式 / 汽车电子工程师（AUTOSAR · CAN/CANFD · DoIP · 域控制器底软）。

单文件静态页面，没有构建步骤：push 到 `main` 就由 GitHub Pages 发布。

**线上地址：<https://zhaojiale2021.github.io/>**

## 页面内容

| 区块 | 内容 |
|---|---|
| 个人画像 | 简介、任职经历时间线、技能标签 |
| 公开项目 | 页面内置的公开仓库数据（剔除 fork 与本仓库），显示语言、话题、更新时间与 README 入口 |
| 私有仓库 | 个人工具链 / AI 效率工程精选（仅展示，卡片标「私有」，不给链接） |

另有浅色 / 深色主题切换、滚动入场动画等，并遵循 `prefers-reduced-motion`。

## 仓库结构

```
index.html                        # 页面全部内容：样式、结构、脚本都在这一个文件里
scripts/sync_repos.py             # 刷新 index.html 里的公开仓库数据（页面的唯一数据源）
.github/workflows/ci.yml          # HTML 结构 / 缓存 JSON / 死链检查
.github/workflows/sync-repos.yml  # 定时刷新内置缓存并提交
.github/workflows/lighthouse.yml  # Lighthouse 性能与无障碍审计
lychee.toml                       # 死链检查配置
lighthouserc.json                 # Lighthouse 审计与评分门槛
```

## 「公开项目」区块是怎么工作的

数据全部来自 `index.html` 里 `<script id="repo-data">` 的 JSON，**页面不请求 GitHub API**：

- 未认证的 GitHub API 限流是 60 次/小时、按出口 IP 共享，公司网络下很容易整体失败；
- 抓取器和无 JS 环境看不到运行时渲染的内容；
- 仓库列表变动很慢，为它付运行时成本不划算。

数据由 `scripts/sync_repos.py` 维护，页面底部会标出「同步于 ……」：

```bash
python scripts/sync_repos.py               # 拉取 GitHub 并写回 index.html
python scripts/sync_repos.py --check       # 离线校验数据格式（CI 用，不联网）
python scripts/sync_repos.py --check-live  # 联网比对数据与线上仓库，只报告不写回
```

脚本只写公开仓库——即使带上 `GITHUB_TOKEN`，私有仓库也不会被写进页面。

## 本地预览

没有构建步骤，直接打开 `index.html`，或起一个静态服务器：

```bash
python -m http.server 8000    # 访问 http://localhost:8000
```

## CI

| Workflow | 触发 | 做什么 |
|---|---|---|
| `ci.yml` | push / PR / 手动 | `html-validate` 校验页面结构；校验内置数据 JSON 的字段、排序与 `synced_at` 格式；`lychee` 检查死链 |
| `sync-repos.yml` | 每周一 + 手动 | 拉取公开仓库刷新页面内置数据并提交（Pages 随之重新发布） |
| `lighthouse.yml` | push / PR / 手动 | LHCI 起本地静态服务器跑审计：无障碍 ≥ 0.9 为门槛，性能 / 最佳实践 / SEO 只给提示 |

私有仓库链接与 `localhost` 预览地址在 `lychee.toml` 里被排除：前者匿名请求必然 404。

`synced_at` 每次同步都会更新，因此每周都会产生一次提交——这同时避免了公共仓库闲置 60 天后，GitHub 自动停掉定时 workflow。

## 相关仓库

公开：

| 仓库 | 说明 |
|---|---|
| [omniview](https://github.com/zhaojiale2021/omniview) | Rust 桌面视频播放器，支持 360° 全景视频（ffmpeg-next + wgpu + egui） |
| [autosar-busmirror-dissector](https://github.com/zhaojiale2021/autosar-busmirror-dissector) | AUTOSAR BusMirror 协议的 Wireshark Lua dissector + 测试报文生成器 |
| [vscode-agent-sdk-update](https://github.com/zhaojiale2021/vscode-agent-sdk-update) | 预置 VS Code / Insiders 的 agent-host SDK 缓存，没有 Copilot 订阅也能用本地 agent |
| [USB2X](https://github.com/zhaojiale2021/USB2X) | 用 STM32 等 MCU 实现 USB 转任意通信协议 |

私有（主页上有简介，仓库本身不可访问）：`CAN_CRC_Checker`、`skills`、`agent-memory`、`doip-test`、`someip-test`、`personal-knowledge-base` 等。

## 说明

仓库目前没有 LICENSE 文件；页面内容如需引用请注明出处。页面上展示的客户 / 项目信息已做泛化处理。
