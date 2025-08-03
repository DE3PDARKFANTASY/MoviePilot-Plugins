"""
MoviePilot 插件：GitHub520 → CheckTMDB 运行时 Hosts
逻辑：
1. 先劫持 GitHub520，确保 GitHub 可达
2. 连通性探测通过后拉取 CheckTMDB
3. 每天 04:00 重复上述流程
"""
from __future__ import annotations

import socket
import time
import ipaddress
from datetime import datetime
from typing import Dict, Tuple, Optional, Any

import requests
from app.plugins import _PluginBase
from app.core.logger import logger

_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_RUNTIME_HOSTS: Dict[str, Tuple[str, socket.AddressFamily]] = {}

# ---------- 工具 ----------
def _is_valid_ip(addr: str) -> bool:
    try:
        ipaddress.ip_address(addr)
        return True
    except ValueError:
        return False

def _load_hosts(url: str) -> Dict[str, Tuple[str, socket.AddressFamily]]:
    """将 hosts 文本解析成 dict"""
    hosts: Dict[str, Tuple[str, socket.AddressFamily]] = {}
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for line in resp.text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if len(parts) >= 2:
                    ip, host = parts[0], parts[-1].lower()
                    if _is_valid_ip(ip):
                        af = socket.AF_INET6 if ":" in ip else socket.AF_INET
                        hosts[host] = (ip, af)
    except Exception as e:
        logger.error("[Runtime Hosts] 拉取 %s 失败: %s", url, e)
    return hosts

def _patch(hosts: Dict[str, Tuple[str, socket.AddressFamily]]) -> None:
    """把 hosts 注入到进程"""
    def _patched(host, port, *a, **kw):
        item = hosts.get(host.lower())
        if item:
            ip, family = item
            return [(family, socket.SOCK_STREAM, 0, "", (ip, port))]
        return _ORIGINAL_GETADDRINFO(host, port, *a, **kw)
    socket.getaddrinfo = _patched

def _probe_github() -> bool:
    """探测 GitHub Raw 是否可达"""
    try:
        requests.head("https://raw.githubusercontent.com", timeout=5).raise_for_status()
        logger.info("[Runtime Hosts] GitHub Raw 连通性 OK")
        return True
    except Exception as e:
        logger.warning("[Runtime Hosts] GitHub Raw 不通: %s", e)
        return False

def _update_all() -> None:
    """完整更新流程：GitHub520 → 探测 → CheckTMDB"""
    # 1. GitHub520
    github_hosts = _load_hosts("https://raw.hellogithub.com/hosts")
    if not github_hosts:
        logger.error("[Runtime Hosts] GitHub520 拉取为空，跳过本次更新")
        return
    _patch(github_hosts)  # 立即生效，解决 GitHub 被墙问题

    # 2. 探测连通性
    if not _probe_github():
        logger.error("[Runtime Hosts] GitHub 仍不可达，放弃拉取 CheckTMDB")
        return

    # 3. 拉取 CheckTMDB
    tmdb_hosts = _load_hosts("https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv4")
    tmdb_hosts.update(_load_hosts("https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv6"))
    github_hosts.update(tmdb_hosts)  # 合并
    _patch(github_hosts)
    logger.info("[Runtime Hosts] 已合并 GitHub520 + CheckTMDB，总计 %d 条", len(github_hosts))

# ---------- 插件 ----------
class Github520TmdbRuntimeHosts(_PluginBase):
    plugin_name = "GitHub520→CheckTMDB Runtime Hosts"
    plugin_desc = "先劫持 GitHub520 解决 GitHub 连通，再拉取 CheckTMDB 双栈 hosts"
    plugin_version = "1.4.0"
    plugin_author = "yourname"

    def init_plugin(self, config: Optional[Dict[str, Any]] = None):
        enabled = bool(config and config.get("enable"))
        if enabled:
            self._enable()
        else:
            self._disable()

    def _enable(self):
        _update_all()
        self._register_job()
        logger.info("[%s] 插件已启用", self.plugin_name)

    def _disable(self):
        self.stop_service()
        socket.getaddrinfo = _ORIGINAL_GETADDRINFO
        _RUNTIME_HOSTS.clear()
        logger.info("[%s] 插件已停用", self.plugin_name)

    def _register_job(self):
        self.stop_service()
        self.scheduler.add_job(
            func=_update_all,
            trigger="cron",
            hour=4,
            minute=0,
            id="runtime_hosts_daily",
            coalesce=True,
            max_instances=1,
        )

    def stop_service(self):
        try:
            self.scheduler.remove_job("runtime_hosts_daily")
        except Exception:
            pass

    def get_state(self) -> bool:
        return bool(self.scheduler.get_job("runtime_hosts_daily"))
