from __future__ import annotations

import socket
import ipaddress
from datetime import datetime, time
from typing import Dict, Tuple, Optional, Any

import requests
from moviepilot.plugins import Plugin
from moviepilot.core.scheduler import add_job, remove_job
from moviepilot.core.logger import logger

_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_RUNTIME_HOSTS: Dict[str, Tuple[str, socket.AddressFamily]] = {}

class GitHub520TMDBRuntimeHosts(Plugin):
    """动态注入 GitHub520 + CheckTMDB 的 hosts 解析规则"""
    
    # 插件元数据 (必须与 package.json 一致)
    plugin_id = "github520_tmdb_runtime_hosts"
    plugin_name = "GitHub520 → CheckTMDB Runtime Hosts"
    plugin_desc = "先劫持 GitHub520 解决 GitHub 连通，再拉取 CheckTMDB 双栈 hosts"
    plugin_icon = "dns"  # 使用 MoviePilot 内置 DNS 图标
    plugin_version = "1.5.0"
    
    # 默认配置
    DEFAULT_CONFIG = {
        "enable": True,
        "update_hour": 4,
        "github_url": "https://raw.hellogithub.com/hosts",
        "tmdb_ipv4_url": "https://raw.githubusercontent.com/cnwikee/CheckTMDB/main/Tmdb_host_ipv4",
        "tmdb_ipv6_url": "https://raw.githubusercontent.com/cnwikee/CheckTMDB/main/Tmdb_host_ipv6",
        "probe_url": "https://api.github.com"
    }
    
    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        """初始化插件"""
        self.config = config or self.DEFAULT_CONFIG
        
        # 启用/禁用插件
        if self.config.get("enable", True):
            self._enable()
        else:
            self._disable()
            
        # 注册定时任务
        self._register_job()
        
        logger.info(f"[{self.plugin_name}] 插件初始化完成")
    
    def _enable(self):
        """启用插件功能"""
        # 首次更新
        self._update_all()
        
        # 保存原始解析函数
        global _ORIGINAL_GETADDRINFO
        _ORIGINAL_GETADDRINFO = socket.getaddrinfo
        
        logger.info(f"[{self.plugin_name}] 插件已启用")

    def _disable(self):
        """禁用插件功能"""
        # 恢复原始解析函数
        socket.getaddrinfo = _ORIGINAL_GETADDRINFO
        
        # 清空缓存
        global _RUNTIME_HOSTS
        _RUNTIME_HOSTS.clear()
        
        logger.info(f"[{self.plugin_name}] 插件已停用")

    def _register_job(self):
        """注册定时任务"""
        # 移除旧任务
        remove_job("runtime_hosts_daily")
        
        # 添加新任务
        if self.config.get("enable", True):
            update_hour = self.config.get("update_hour", 4)
            add_job(
                func=self._update_all,
                trigger="cron",
                hour=update_hour,
                id="runtime_hosts_daily",
                name="每日Hosts更新",
                coalesce=True,
                max_instances=1
            )
            logger.info(f"[{self.plugin_name}] 已注册每日 {update_hour}:00 更新任务")

    def stop_plugin(self):
        """停止插件时调用"""
        self._disable()
        remove_job("runtime_hosts_daily")
        logger.info(f"[{self.plugin_name}] 插件已停止")

    def get_state(self) -> bool:
        """获取插件状态"""
        return bool(self.config.get("enable", True))

    def get_form(self) -> Dict[str, Any]:
        """返回配置表单"""
        return {
            "enable": {
                "type": "switch",
                "label": "启用插件",
                "default": True
            },
            "update_hour": {
                "type": "number",
                "label": "每日更新时间",
                "default": 4,
                "min": 0,
                "max": 23,
                "help": "UTC时间，0-23点"
            },
            "github_url": {
                "type": "text",
                "label": "GitHub520 URL",
                "default": self.DEFAULT_CONFIG["github_url"],
                "help": "GitHub520 hosts文件地址"
            },
            "tmdb_ipv4_url": {
                "type": "text",
                "label": "TMDB IPv4 URL",
                "default": self.DEFAULT_CONFIG["tmdb_ipv4_url"],
                "help": "TMDB IPv4 hosts文件地址"
            },
            "tmdb_ipv6_url": {
                "type": "text",
                "label": "TMDB IPv6 URL",
                "default": self.DEFAULT_CONFIG["tmdb_ipv6_url"],
                "help": "TMDB IPv6 hosts文件地址"
            },
            "probe_url": {
                "type": "text",
                "label": "连通性测试URL",
                "default": self.DEFAULT_CONFIG["probe_url"],
                "help": "用于测试GitHub连通性的URL"
            }
        }

    def _is_valid_ip(self, addr: str) -> bool:
        """验证IP地址格式"""
        try:
            ipaddress.ip_address(addr)
            return True
        except ValueError:
            return False

    def _load_hosts(self, url: str) -> Dict[str, Tuple[str, socket.AddressFamily]]:
        """加载hosts文件并解析为字典"""
        hosts = {}
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            
            for line in resp.text.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip, host = parts[0], parts[-1].lower()
                        if self._is_valid_ip(ip):
                            af = socket.AF_INET6 if ":" in ip else socket.AF_INET
                            hosts[host] = (ip, af)
            
            logger.info(f"[{self.plugin_name}] 成功加载 {len(hosts)} 条记录 from {url}")
            return hosts
            
        except Exception as e:
            logger.error(f"[{self.plugin_name}] 加载 {url} 失败: {str(e)}")
            return {}

    def _patch_dns(self, hosts: Dict[str, Tuple[str, socket.AddressFamily]]):
        """劫持DNS解析"""
        def patched_getaddrinfo(host, port, *a, **kw):
            item = hosts.get(host.lower())
            if item:
                ip, family = item
                return [(family, socket.SOCK_STREAM, 0, "", (ip, port))]
            return _ORIGINAL_GETADDRINFO(host, port, *a, **kw)
        
        socket.getaddrinfo = patched_getaddrinfo
        logger.info(f"[{self.plugin_name}] DNS劫持已生效")

    def _probe_connectivity(self, url: str) -> bool:
        """测试网络连通性"""
        try:
            resp = requests.head(url, timeout=5)
            resp.raise_for_status()
            logger.info(f"[{self.plugin_name}] {url} 连通性测试成功")
            return True
        except Exception as e:
            logger.warning(f"[{self.plugin_name}] {url} 连通性测试失败: {str(e)}")
            return False

    def _update_all(self):
        """完整更新流程"""
        logger.info(f"[{self.plugin_name}] 开始更新hosts")
        
        # 1. 加载GitHub520 hosts
        github_hosts = self._load_hosts(self.config["github_url"])
        if not github_hosts:
            logger.error(f"[{self.plugin_name}] GitHub520 hosts加载失败，跳过更新")
            return
            
        # 临时应用GitHub520
        self._patch_dns(github_hosts)
        
        # 2. 连通性测试
        if not self._probe_connectivity(self.config["probe_url"]):
            logger.error(f"[{self.plugin_name}] GitHub连通性测试失败，跳过TMDB更新")
            return
            
        # 3. 加载TMDB hosts
        tmdb_hosts = self._load_hosts(self.config["tmdb_ipv4_url"])
        tmdb_hosts.update(self._load_hosts(self.config["tmdb_ipv6_url"]))
        
        # 合并hosts
        combined_hosts = {**github_hosts, **tmdb_hosts}
        logger.info(f"[{self.plugin_name}] 合并后总计 {len(combined_hosts)} 条记录")
        
        # 4. 应用最终hosts
        self._patch_dns(combined_hosts)
        
        # 5. 更新全局缓存
        global _RUNTIME_HOSTS
        _RUNTIME_HOSTS = combined_hosts
        
        logger.info(f"[{self.plugin_name}] hosts更新完成")

# 插件入口函数
def create_plugin():
    return GitHub520TMDBRuntimeHosts()