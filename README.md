# MoviePilot-Plugins

MoviePilot 第三方插件市场（AI 辅助改造版）。

本仓库目录结构、插件命名规范与官方 [jxxghp/MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins) 保持一致（插件位于 `plugins/` 目录，插件目录名 / 类名 / 中文名均沿用官方规范）。

> 声明：本仓库为 AI 辅助改造版本，部分插件基于官方或社区原作增强功能，原作版权归原作者所有。

## 插件列表

| 插件 | 说明 | 原作 | 版本 |
| --- | --- | --- | --- |
| [customhosts](plugins/customhosts) | 自定义 Hosts：支持定时从 CheckTMDB 自动更新 TMDB/TheTVDB/IMDb 等域名 IP（默认每 6 小时） | [thsrite](https://github.com/thsrite) | 2.0.0 |

## 安装

在 MoviePilot「设置 - 插件市场」中添加本仓库：

- **仓库地址**：`https://github.com/DE3PDARKFANTASY/moviepilot-plugins`
- **分支**：`main`
- **目录**：`plugins`（默认值）

## customhosts（自定义 Hosts）

原作：[thsrite](https://github.com/thsrite) 开发的 [customhosts](https://github.com/jxxghp/MoviePilot-Plugins/tree/main/plugins/customhosts) 插件（v1.2.1）。

本仓库中的 **v2.0.0 由 AI 在保留全部原功能的基础上改造**，改动如下：

### 新增功能

- **定时自动更新 CheckTMDB hosts**：默认每 6 小时从 [cnwikee/CheckTMDB](https://github.com/cnwikee/CheckTMDB) 拉取 TMDB / TheTVDB / IMDb / Fanart / Trakt 等域名 IP，写入系统 hosts（使用 MoviePilot 官方 `get_service()` + `interval` 触发器注册定时任务）
- IPv4 / IPv6 hosts 独立开关，两个下载地址均可配置
- 启用插件时立即执行一次更新，无需等待定时周期
- 配置页展示「最近更新时间」记录（保留最近 5 次）
- 下载自动携带 MoviePilot 代理配置（`PROXY_HOST`），国内访问 GitHub raw 亦可生效

### 问题修复

- 修复原版中空行 / 纯空白行被误判为「错误 hosts」的问题（先 trim 再判空）

### 配置项

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `enabled` | 启用插件 | `False` |
| `auto_update` | 自动更新 CheckTMDB | `True` |
| `update_interval` | 更新间隔（小时） | `6` |
| `use_ipv4` | 使用 IPv4 hosts | `True` |
| `use_ipv6` | 使用 IPv6 hosts | `False` |
| `url_v4` | CheckTMDB IPv4 hosts 下载地址 | `https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv4` |
| `url_v6` | CheckTMDB IPv6 hosts 下载地址 | `https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv6` |
| `hosts` | 手动自定义 hosts（追加在自动更新内容之后，格式：`ip host1 host2 ...`） | 空 |
| `err_hosts` | 错误的 hosts 展示（只读，不会写入系统） | 空 |
| `update_times` | 最近更新时间记录（只读） | 空 |

### 注意事项

- 容器部署时更新的是**容器内**的 `/etc/hosts`，不是宿主机
- 国内环境访问 `raw.githubusercontent.com` 建议在 MoviePilot 中配置网络代理，否则拉取可能失败

## 许可证

插件版权归原作者所有，AI 改造部分遵循原插件相同的许可协议发布。
