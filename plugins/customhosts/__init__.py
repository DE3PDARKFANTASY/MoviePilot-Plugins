from datetime import datetime
from typing import Any, Dict, List, Tuple

from python_hosts import Hosts, HostsEntry

from app.core.config import settings
from app.core.event import eventmanager
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType
from app.utils.http import RequestUtils
from app.utils.ip import IpUtils
from app.utils.system import SystemUtils

# CheckTMDB 默认下载地址（每日自动更新 TMDB/TheTVDB/IMDb 等域名IP）
DEFAULT_URL_V4 = "https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv4"
DEFAULT_URL_V6 = "https://raw.githubusercontent.com/cnwikee/CheckTMDB/refs/heads/main/Tmdb_host_ipv6"
# 定时任务ID
SERVICE_ID = "CustomHostsCheckTMDB"
# 系统hosts中的插件标记
PLUGIN_TAG = "# CustomHostsPlugin"


class CustomHosts(_PluginBase):
    # 插件名称
    plugin_name = "自定义Hosts"
    # 插件描述
    plugin_desc = "修改系统hosts文件，加速网络访问；支持定时从CheckTMDB自动更新TMDB/TheTVDB/IMDb等域名IP（默认每6小时）。"
    # 插件图标
    plugin_icon = "hosts.png"
    # 插件版本
    plugin_version = "2.0.0"
    # 插件作者
    plugin_author = "thsrite"
    # 作者主页
    author_url = "https://github.com/thsrite"
    # 插件配置项ID前缀
    plugin_config_prefix = "customhosts_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _hosts = []
    _auto_update = False
    _update_interval = 6
    _use_ipv4 = True
    _use_ipv6 = False
    _url_v4 = DEFAULT_URL_V4
    _url_v6 = DEFAULT_URL_V6
    _err_hosts = ""
    _update_times = ""

    def init_plugin(self, config: dict = None):
        # 读取配置
        if not config:
            self.__clear_system_hosts()
            return
        self._enabled = config.get("enabled") or False
        self._hosts = config.get("hosts") or ""
        if isinstance(self._hosts, str):
            self._hosts = str(self._hosts).split('\n')
        self._auto_update = config.get("auto_update") or False
        try:
            self._update_interval = int(config.get("update_interval") or 6)
        except Exception:
            self._update_interval = 6
        if self._update_interval <= 0:
            self._update_interval = 6
        self._use_ipv4 = config.get("use_ipv4", True)
        self._use_ipv6 = config.get("use_ipv6", False)
        self._url_v4 = config.get("url_v4") or DEFAULT_URL_V4
        self._url_v6 = config.get("url_v6") or DEFAULT_URL_V6
        self._err_hosts = config.get("err_hosts") or ""
        self._update_times = config.get("update_times") or ""

        # 排除空的host
        new_hosts = []
        for host in self._hosts:
            if host and host != '\n':
                new_hosts.append(host.replace("\n", "") + "\n")
        self._hosts = new_hosts

        if self._enabled and (self._hosts or self._auto_update):
            # 启用且配置了内容（手动或自动），立即刷新一次hosts（含远程拉取）
            self.__refresh_hosts()
        else:
            # hosts为空或未启用，清除系统hosts
            self.__clear_system_hosts()
            self._enabled = False

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务：定时更新CheckTMDB hosts
        """
        if self._enabled and self._auto_update:
            return [{
                "id": SERVICE_ID,
                "name": "定时更新CheckTMDB Hosts",
                "trigger": "interval",
                "func": self.__auto_update_job,
                "kwargs": {"hours": self._update_interval}
            }]
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'auto_update',
                                            'label': '自动更新CheckTMDB',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'update_interval',
                                            'label': '更新间隔（小时）',
                                            'type': 'number',
                                            'hint': '自动更新CheckTMDB的间隔时长，默认6小时'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'use_ipv4',
                                            'label': '使用IPv4',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'use_ipv6',
                                            'label': '使用IPv6',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'url_v4',
                                            'label': 'CheckTMDB IPv4 hosts地址'
                                        }
                                    },
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'url_v6',
                                            'label': 'CheckTMDB IPv6 hosts地址'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'hosts',
                                            'label': '自定义hosts（自动更新内容之后追加）',
                                            'rows': 6,
                                            'placeholder': '每行一个配置，格式为：ip host1 host2 ...'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'err_hosts',
                                            'readonly': True,
                                            'label': '错误hosts',
                                            'rows': 2,
                                            'placeholder': '错误的hosts配置会展示在此处，请修改上方hosts重新提交（错误的hosts不会写入系统hosts文件）'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'update_times',
                                            'readonly': True,
                                            'label': '最近更新时间',
                                            'rows': 3,
                                            'placeholder': '每次自动更新成功后会在此记录时间'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '开启自动更新后，插件会每N小时从CheckTMDB拉取TMDB/TheTVDB/IMDb等域名IP写入系统hosts。'
                                                    '（注：容器运行则更新容器hosts！非宿主机！）'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "auto_update": True,
            "update_interval": 6,
            "use_ipv4": True,
            "use_ipv6": False,
            "url_v4": DEFAULT_URL_V4,
            "url_v6": DEFAULT_URL_V6,
            "hosts": "",
            "err_hosts": "",
            "update_times": ""
        }

    def get_page(self) -> List[dict]:
        pass

    @staticmethod
    def __read_system_hosts():
        """
        读取系统hosts对象
        """
        # 获取本机hosts路径
        if SystemUtils.is_windows():
            hosts_path = r"c:\windows\system32\drivers\etc\hosts"
        else:
            hosts_path = '/etc/hosts'
        # 读取系统hosts
        return Hosts(path=hosts_path)

    def __clear_system_hosts(self):
        """
        清除系统hosts
        """
        # 系统hosts对象
        system_hosts = self.__read_system_hosts()
        # 过滤掉插件添加的hosts
        orgin_entries = []
        for entry in system_hosts.entries:
            if entry.entry_type == "comment" and entry.comment == PLUGIN_TAG:
                break
            orgin_entries.append(entry)
        system_hosts.entries = orgin_entries
        try:
            system_hosts.write()
            logger.info("系统hosts文件已恢复")
        except Exception as err:
            logger.error(f"恢复系统hosts文件失败：{str(err) or '请检查权限'}")
            # 推送实时消息
            self.systemmessage.put(f"恢复系统hosts文件失败：{str(err) or '请检查权限'}", title="自定义Hosts")

    def __add_hosts_to_system(self, hosts):
        """
        添加hosts到系统
        """
        # 系统hosts对象
        system_hosts = self.__read_system_hosts()
        # 过滤掉插件添加的hosts
        orgin_entries = []
        for entry in system_hosts.entries:
            if entry.entry_type == "comment" and entry.comment == PLUGIN_TAG:
                break
            orgin_entries.append(entry)
        system_hosts.entries = orgin_entries
        # 新的有效hosts
        new_entrys = []
        # 新的错误的hosts
        err_hosts = []
        err_flag = False
        for host in hosts:
            if not host or not str(host).strip():
                continue
            host = str(host).strip()
            if host.startswith('#'):  # 检查是否为注释行
                host_entry = HostsEntry(entry_type='comment', comment=host)
                new_entrys.append(host_entry)
                continue

            host_arr = str(host).split()
            try:
                host_entry = HostsEntry(entry_type='ipv4' if IpUtils.is_ipv4(str(host_arr[0])) else 'ipv6',
                                        address=host_arr[0],
                                        names=host_arr[1:])
                new_entrys.append(host_entry)
            except Exception as err:
                err_hosts.append(host + "\n")
                logger.error(f"[HOST] 格式转换错误：{str(err)}")
                # 推送实时消息
                self.systemmessage.put(f"[HOST] 格式转换错误：{str(err)}", title="自定义Hosts")

        # 写入系统hosts
        if new_entrys:
            try:
                # 添加分隔标识
                system_hosts.add([HostsEntry(entry_type='comment', comment=PLUGIN_TAG)])
                # 添加新的Hosts
                system_hosts.add(new_entrys)
                system_hosts.write()
                logger.info("更新系统hosts文件成功")
            except Exception as err:
                err_flag = True
                logger.error(f"更新系统hosts文件失败：{str(err) or '请检查权限'}")
                # 推送实时消息
                self.systemmessage.put(f"更新系统hosts文件失败：{str(err) or '请检查权限'}", title="自定义Hosts")
        return err_flag, ''.join(err_hosts)

    def __refresh_hosts(self, send_message: bool = False):
        """
        刷新系统hosts：自动更新（CheckTMDB远程）+ 手动自定义
        """
        hosts_list = []
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 1. 自动更新：拉取CheckTMDB远程hosts
        if self._auto_update:
            remote_hosts, fetch_err = self.__fetch_remote_hosts()
            if remote_hosts:
                hosts_list.extend(remote_hosts.split('\n'))
                logger.info("CheckTMDB远程hosts拉取成功")
            else:
                logger.warning(f"CheckTMDB远程hosts拉取失败：{fetch_err or '未知错误'}")
                if send_message:
                    self.systemmessage.put(
                        f"CheckTMDB远程hosts拉取失败：{fetch_err or '请检查网络或代理配置'}", title="自定义Hosts")
        # 2. 手动自定义hosts追加在后面
        hosts_list.extend(self._hosts)

        # 3. 没有可用内容则清除系统hosts
        if not hosts_list:
            self.__clear_system_hosts()
            self._enabled = False
            self.update_config({"enabled": False})
            return

        # 4. 写入系统hosts
        error_flag, err_hosts = self.__add_hosts_to_system(hosts_list)
        self._err_hosts = err_hosts
        if not error_flag:
            # 记录最近5次更新时间
            new_times = f"{now}\n{self._update_times}".strip()
            self._update_times = "\n".join(new_times.split("\n")[:5])
            logger.info(f"系统hosts更新完成：{now}")

        # 5. 回写配置
        self.update_config({
            "hosts": ''.join(self._hosts),
            "err_hosts": self._err_hosts,
            "enabled": self._enabled,
            "auto_update": self._auto_update,
            "update_interval": self._update_interval,
            "use_ipv4": self._use_ipv4,
            "use_ipv6": self._use_ipv6,
            "url_v4": self._url_v4,
            "url_v6": self._url_v6,
            "update_times": self._update_times
        })

    def __fetch_remote_hosts(self) -> Tuple[str, str]:
        """
        从CheckTMDB拉取远程hosts内容
        :return: (hosts内容, 错误信息)，内容为空表示拉取失败
        """
        contents = []
        errors = []
        # 代理配置（国内访问GitHub raw建议配置）
        proxies = None
        proxy_host = getattr(settings, "PROXY_HOST", None)
        if proxy_host:
            proxies = {"http": proxy_host, "https": proxy_host}

        if self._use_ipv4:
            content = RequestUtils(proxies=proxies, timeout=30).get(self._url_v4)
            if content:
                contents.append("# ---------- CheckTMDB IPv4 ----------")
                contents.append(content)
            else:
                errors.append("IPv4下载失败")
        if self._use_ipv6:
            content = RequestUtils(proxies=proxies, timeout=30).get(self._url_v6)
            if content:
                contents.append("# ---------- CheckTMDB IPv6 ----------")
                contents.append(content)
            else:
                errors.append("IPv6下载失败")
        if not contents:
            return "", "；".join(errors)
        return "\n".join(contents), ""

    def __auto_update_job(self):
        """
        定时任务：按间隔自动更新CheckTMDB hosts
        """
        logger.info(f"开始定时更新CheckTMDB Hosts（间隔{self._update_interval}小时）")
        self.__refresh_hosts(send_message=True)

    def stop_service(self):
        """
        退出插件
        """
        pass

    @eventmanager.register(EventType.PluginReload)
    def reload(self, event):
        """
        响应插件重载事件
        """
        plugin_id = event.event_data.get("plugin_id")
        if not plugin_id:
            return
        if plugin_id != self.__class__.__name__:
            return
        return self.init_plugin(self.get_config())
