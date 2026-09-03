from __future__ import annotations

import base64
import gzip
import hashlib
import html
import json
import os
import platform
import random
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
import urllib3
import yaml

# 代理设置（Clash 的 HTTP 端口）
PROXIES = None

# 关闭 SSL 警告（配合 verify=False）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

VERSION = "modified"
OUTPUT_PATH = Path("output/clash.yaml")
RAW_PATH = Path("output/raw.yaml")
HISTORY_DIR = Path("history")
TEST_URL = "http://www.gstatic.com/generate_204"
SOURCE_TIMEOUT = 25
LATENCY_TIMEOUT_MS = 5000
MAX_RETRIES = 3
MAX_WORKERS = int(os.getenv("FREE_NODE_AUTOTEST_MAX_WORKERS", "24"))
MAX_CANDIDATES = int(os.getenv("FREE_NODE_AUTOTEST_MAX_CANDIDATES", "0"))
MAX_LIVE_PER_SOURCE = int(os.getenv("FREE_NODE_AUTOTEST_MAX_LIVE_PER_SOURCE", "45"))

SOURCE_GROUPS = [
    {
        "name": "大FQ运动",
        "primary": "discover:sublink:https://end-gfw.com/",
        "fallbacks": [
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together",
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/refs/heads/main/clash.yaml",
            "discover:sublink:https://raw.githubusercontent.com/hello-world-1989/cn-news/refs/heads/main/README.md",
        ],
        "prefix": "[大FQ运动] ",
    },
    {
        "name": "大FQ运动-SS密钥",
        "primary": "https://end-gfw.com/ss-key",
        "fallbacks": [
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together-ss",
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together",
        ],
        "referer": "https://end-gfw.com/",
        "prefix": "[大FQ运动-SS密钥] ",
    },
    {
        "name": "大FQ运动-补充",
        "primary": "discover:sublink:https://github.com/hello-world-1989/cn-news/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/hello-world-1989/v2-sub/main/end-gfw-together-af3e13",
        ],
        "prefer": "速度更快",
        "exclude": "end-gfw.com",
        "prefix": "[大FQ运动-补充] ",
    },
    {
        "name": "ChromeGO-工具包",
        "primary": "discover:toolkit:https://github.com/bannedbook/fanqiang/releases",
        "fallbacks": [],
        "prefer": "ChromeGo",
        "prefix": "[ChromeGO-工具包] ",
    },
    {
        "name": "ChromeGO-ShiteThings",
        "primary": "discover:sublink:https://raw.githubusercontent.com/ShiteThings/extractNodes/refs/heads/main/README.md",
        "fallbacks": [
            "https://chg26.makou.cc.cd/",
        ],
        "prefix": "[ChromeGO-ShiteThings] ",
    },
    {
        "name": "ChromeGO-Merge",
        "primary": "discover:sublink:https://github.com/Misaka-blog/chromego_merge/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://chromego-sub.netlify.app/sub/merged_proxies_new.yaml",
            "https://chromego-sub.netlify.app/sub/base64.txt",
        ],
        "prefix": "[ChromeGO-Merge] ",
    },
    {
        "name": "Freesocks",
        "primary": "https://freesocks.org/api/v1/sub/02b897e8e77f19176b0b9f2c75864b00",
        "fallbacks": [],
        "prefix": "[Freesocks] ",
    },
    {
        "name": "NEKOWARP",
        "primary": "https://neko-warp.nloli.xyz/neko_warp.yaml",
        "fallbacks": [],
        "prefix": "[NEKOWARP] ",
    },
    {
        "name": "V2Rayshare-RSS",
        "primary": "discover:article:https://v2rayshare.com/feed",
        "fallbacks": [],
        "prefix": "[V2Rayshare-RSS] ",
    },
    {
        "name": "OpenRunner-RSS",
        "primary": "discover:article:https://free.datiya.com/index.xml",
        "fallbacks": [
            "https://raw.githubusercontent.com/openRunner/clash-freenode/main/sub.yaml",
            "https://raw.githubusercontent.com/openRunner/clash-freenode/main/clash.yaml",
            "https://raw.githubusercontent.com/openrunner/clash-freenode/main/clash.yaml",
        ],
        "prefix": "[OpenRunner-RSS] ",
    },
    {
        "name": "Mibei77-RSS",
        "primary": "discover:article:https://www.mibei77.com/feed",
        "fallbacks": [],
        "prefix": "[Mibei77-RSS] ",
    },
    {
        "name": "Yoyapai-RSS",
        "primary": "discover:article:https://yoyapai.com/feed",
        "fallbacks": [],
        "prefix": "[Yoyapai-RSS] ",
    },
    {
        "name": "Free-clash-v2ray",
        "primary": "discover:sublink:https://raw.githubusercontent.com/free-clash-v2ray/free-clash-v2ray.github.io/main/README.md",
        "fallbacks": [
            "https://free-clash-v2ray.github.io/uploads/latest.yaml",
        ],
        "prefer": "3-",
        "prefix": "[Free-clash-v2ray] ",
    },
    {
        "name": "Pawdroid-Base64",
        "primary": "https://raw.githubusercontent.com/Pawdroid/Free-servers/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://mirror.v2gh.com/https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        ],
        "prefix": "[Pawdroid-Base64] ",
    },
    {
        "name": "FreeV2-Base64",
        "primary": "https://xmxosfepggzm.503403.xyz",
        "fallbacks": [],
        "prefix": "[FreeV2-Base64] ",
    },
    {
        "name": "Bocchi2b-Base64",
        "primary": "https://links.bocchi2b.top/clash",
        "fallbacks": [],
        "user_agent": "Chrome",
        "prefix": "[Bocchi2b-Base64] ",
    },
    {
        "name": "V2Rayshare-订阅",
        "primary": "discover:sublink:https://github.com/firefoxmmx2/v2rayshare_subcription/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://cdn.jsdelivr.net/gh/firefoxmmx2/v2rayshare_subcription/subscription/mihomo_sub.yaml",
        ],
        "prefix": "[V2Rayshare-订阅] ",
    },
    {
        "name": "免费节点1",
        "primary": "discover:sublink:https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml",
        ],
        "prefix": "[免费节点1] ",
    },
    {
        "name": "免费节点1-自建",
        "primary": "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/README.md",
        "fallbacks": [],
        "prefix": "[免费节点1-自建] ",
    },
    {
        "name": "免费节点2",
        "primary": "discover:sublink:https://github.com/ermaozi/get_subscribe/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
        ],
        "prefix": "[免费节点2] ",
    },
    {
        "name": "免费节点3",
        "primary": "discover:sublink:https://raw.githubusercontent.com/sunmiao4458/free-proxy-airport/refs/heads/main/README.md",
        "fallbacks": [
            "https://sunmiao4458.github.io/free-proxy-airport/clash.yaml",
        ],
        "prefix": "[免费节点3] ",
    },
    {
        "name": "免费节点4",
        "primary": "discover:sublink:https://raw.githubusercontent.com/mfuu/FreeProxies/refs/heads/master/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/mfuu/FreeProxies/master/sub.yaml",
        ],
        "prefix": "[免费节点4] ",
    },
    {
        "name": "免费节点5",
        "primary": "discover:sublink:https://github.com/vxiaov/free_proxies/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
            "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml",
        ],
        "prefix": "[免费节点5] ",
    },
    {
        "name": "免费节点6",
        "primary": "discover:sublink:https://github.com/anaer/Sub/raw/refs/heads/main/README.MD",
        "fallbacks": [
            "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
            "https://anaer.github.io/Sub/clash.yaml",
        ],
        "prefix": "[免费节点6] ",
    },
    {
        "name": "免费节点7",
        "primary": "discover:sublink:https://github.com/snakem982/proxypool/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/snakem982/proxypool/main/source/clash-meta-2.yaml",
        ],
        "prefix": "[免费节点7] ",
    },
    {
        "name": "免费节点8",
        "primary": "discover:sublink:https://raw.githubusercontent.com/mahdibland/V2RayAggregator/refs/heads/master/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/mahdibland/SSAggregator/master/sub/sub_merge_yaml.yml",
        ],
        "prefer": "sub_merge",
        "prefix": "[免费节点8] ",
    },
    {
        "name": "免费节点9-1",
        "primary": "discover:sublink:https://raw.githubusercontent.com/w1770946466/Auto_proxy/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription_num",
        ],
        "prefer": "subscription_num",
        "prefix": "[免费节点9-1] ",
    },
    {
        "name": "免费节点9-2",
        "primary": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription_try",
        "fallbacks": [],
        "prefix": "[免费节点9-2] ",
    },
    {
        "name": "免费节点10",
        "primary": "discover:sublink:https://raw.githubusercontent.com/PuddinCat/BestClash/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/PuddinCat/BestClash/refs/heads/main/proxies.yaml",
        ],
        "prefer": "订阅地址",
        "prefix": "[免费节点10] ",
    },
    {
        "name": "免费节点11-1",
        "primary": "discover:sublink:https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/base64.txt",
            "https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/all.yaml",
            "https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/mihomo.yaml",
        ],
        "prefer": "订阅链接",
        "prefix": "[免费节点11-1] ",
    },
    {
        "name": "免费节点11-2",
        "primary": "https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/byxiaoxi.txt",
        "fallbacks": [],
        "prefix": "[免费节点11-2] ",
    },
    {
        "name": "免费节点11-3",
        "primary": "https://raw.githubusercontent.com/kooker/FreeSubsCheck/main/kooker.jp.txt",
        "fallbacks": [],
        "prefix": "[免费节点11-3] ",
    },
    {
        "name": "Clashfree",
        "primary": "discover:sublink:https://raw.githubusercontent.com/free-nodes/clashfree/refs/heads/main/README.md",
        "fallbacks": [
            {
                "url": "discover:sublink:https://raw.githubusercontent.com/free-nodes/v2rayfree/refs/heads/main/README.md",
                "prefer": "订阅地址",
            },
            "https://raw.githubusercontent.com/free-nodes/v2rayfree/main/sub",
        ],
        "prefix": "[Clashfree] ",
    },
    {
        "name": "Epodonios-v2ray-configs",
        "primary": "discover:sublink:https://github.com/Epodonios/v2ray-configs/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt",
        ],
        "prefer": "All_Configs",
        "prefix": "[Epodonios-v2ray-configs] ",
    },
    {
        "name": "V2rayclashfree-RSS",
        "primary": "discover:article:https://v2rayclashfree.com/",
        "fallbacks": [],
        "prefix": "[V2rayclashfree-RSS] ",
    },
]

SUPPORTED_PROXY_TYPES = {
    "ss",
    "ssr",
    "vmess",
    "vless",
    "trojan",
    "hysteria",
    "hysteria2",
    "hy2",
    "tuic",
    "socks5",
    "http",
    "wireguard",
}

REQUIRED_GROUPS = (
    "URL-TEST",
    "HK-POOL",
    "JP-POOL",
    "US-POOL",
    "FAST-POOL",
    "FALLBACK",
    "PROXY",
)


@dataclass
class ProxyMetric:
    proxy: dict[str, Any]
    latency: int
    region: str
    health_score: float


UA_PRESETS = {
    "ClashMeta": "ClashMeta/1.19.30",
    "Chrome": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def resolve_ua(name: str = "") -> str:
    key = (name or "ClashMeta").strip()
    return UA_PRESETS.get(key, key)


def _writable_dir(name: str) -> Path:
    bases = []
    try:
        bases.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        bases.append(Path(os.getcwd()))
    except OSError:
        pass
    bases.append(Path.home())
    last_exc: Exception | None = None
    for base in bases:
        target = base / name
        try:
            os.makedirs(str(target), exist_ok=True)
            probe = target / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return target
        except OSError as exc:
            last_exc = exc
    raise RuntimeError(f"cannot create {name} directory: {last_exc}")


def _bind_dirs() -> None:
    global OUTPUT_PATH, RAW_PATH, HISTORY_DIR
    output_dir = _writable_dir("output")
    OUTPUT_PATH = output_dir / "clash.yaml"
    RAW_PATH = output_dir / "raw.yaml"
    HISTORY_DIR = _writable_dir("history")


def fetch_text(
    url: str,
    retries: int = MAX_RETRIES,
    user_agent: str = "",
    referer: str = "",
    accept: str = "",
) -> str:
    headers = {
        "User-Agent": resolve_ua(user_agent),
        "Accept": accept or "text/plain, text/yaml, application/yaml, */*",
    }
    if referer:
        headers["Referer"] = referer
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    proxy_tries = [PROXIES, {}] if PROXIES else [{}]
    last_error: Exception | None = None
    for proxies in proxy_tries:
        for attempt in range(1, retries + 1):
            try:
                response = session.get(
                    url,
                    headers=headers,
                    timeout=SOURCE_TIMEOUT,
                    proxies=proxies,
                )
                response.raise_for_status()
                return response.content.decode("utf-8", errors="replace")
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(2 * attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def maybe_base64_decode(text: str) -> str:
    compact = "".join(text.split())
    if not compact or len(compact) % 4 != 0:
        return text
    if not re.fullmatch(r"[A-Za-z0-9+/=]+", compact):
        return text
    try:
        decoded = base64.b64decode(compact, validate=True).decode("utf-8")
    except Exception:
        return text
    return decoded if "proxies:" in decoded or "://" in decoded else text


_YAML_WARN_SEEN: set[str] = set()
_YAML_WARN_SILENT = False


def _yaml_warn(brief: str) -> None:
    if _YAML_WARN_SILENT:
        return
    key = re.sub(r"\s*skipped=\d+", "", brief).strip()
    if not key or key in _YAML_WARN_SEEN:
        return
    _YAML_WARN_SEEN.add(key)
    print(f"[WARN] YAML parse failed: {brief}")


def _yaml_error_brief(exc: Exception) -> str:
    text = str(exc)
    name = ""
    match = re.search(r"name:\s*(.+)", text)
    if match:
        name = match.group(1).split(",")[0].strip().strip("'\"")
        name = re.sub(r"\s+", " ", name)[:80]
    snippet = ""
    mark = getattr(exc, "problem_mark", None)
    if mark is not None:
        try:
            snippet = " ".join(str(mark.get_snippet() or "").split())[:80]
        except Exception:
            snippet = ""
        if not snippet:
            snippet = f"line {mark.line + 1} col {mark.column + 1}"
    if not snippet:
        line_match = re.search(r"column \d+:\s*\n\s*(.+)", text)
        if line_match:
            snippet = line_match.group(1).strip()[:80]
    reason = "YAML syntax"
    if "expected ',' or '}'" in text:
        reason = "broken quotes in flow mapping"
    elif "while scanning" in text:
        reason = "YAML scan error"
    bits = [reason]
    if name:
        bits.append(f"name={name}")
    if snippet:
        bits.append(f"at={snippet}")
    return " ".join(bits)


def load_yaml_document(text: str) -> Any:
    try:
        return yaml.safe_load(maybe_base64_decode(text))
    except yaml.YAMLError as exc:
        _yaml_warn(_yaml_error_brief(exc))
        return None


def extract_proxy_block(text: str) -> list[Any]:
    lines = maybe_base64_decode(text).splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if re.match(r"^proxies\s*:\s*$", line):
            start = index
            break
    if start is None:
        # 有些源直接是纯列表，没有 proxies: 头部，整文件当 block 处理
        block = lines
    else:
        block = []
        for line in lines[start + 1 :]:
            if line and not line.startswith((" ", "\t", "-")) and re.match(r"^[A-Za-z0-9_-]+\s*:", line):
                break
            block.append(line)

    # 1. 先尝试完整解析
    yaml_fail = ""
    try:
        parsed = yaml.safe_load("proxies:\n" + "\n".join(block))
        if isinstance(parsed, dict) and isinstance(parsed.get("proxies"), list):
            return parsed["proxies"]
    except yaml.YAMLError as exc:
        yaml_fail = _yaml_error_brief(exc)

    proxies: list[Any] = []
    skipped = 0
    for line in block:
        stripped = line.strip()
        if not stripped or not stripped.startswith("-"):
            continue
        try:
            item = yaml.safe_load(stripped)
            if isinstance(item, list) and item and isinstance(item[0], dict):
                proxies.append(item[0])
            elif isinstance(item, dict):
                proxies.append(item)
        except yaml.YAMLError:
            skipped += 1
            continue
    if yaml_fail:
        extra = f" skipped={skipped}" if skipped else ""
        _yaml_warn(f"{yaml_fail}{extra}")
    elif skipped:
        _yaml_warn(f"skipped {skipped} invalid proxy line(s)")
    return proxies


_SHARE_URI_RE = re.compile(
    r"(?:ss|ssr|vmess|vless|trojan|hysteria2?|hy2|tuic|socks5h?|socks|wireguard)://",
    re.IGNORECASE,
)


def extract_share_uris(text: str) -> list[str]:
    stripped = re.sub(r"<[^>]+>", " ", text)
    starts = list(_SHARE_URI_RE.finditer(stripped))
    if not starts:
        return []
    uris: list[str] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(stripped)
        piece = stripped[match.start():end].split("```")[0]
        scheme = match.group(0).split("://", 1)[0].lower()
        if scheme == "vmess":
            body = re.match(r"vmess://[A-Za-z0-9+/=\s]+", piece, re.I)
            if not body:
                continue
            chunk = re.sub(r"\s+", "", body.group(0))
            frag = re.match(r"#[^\s`#]+", piece[body.end():])
            if frag:
                chunk += frag.group(0)
        else:
            chunk = re.split(r"\s+", piece, maxsplit=1)[0]
        chunk = re.split(r"[<>\"']", chunk)[0]
        if "://" in chunk:
            uris.append(chunk)
    return uris


_SINGBOX_SKIP_TYPES = {
    "direct", "block", "dns", "selector", "urltest", "loadbalance",
    "pass", "reject", "compatible",
}


def _singbox_tls(proxy: dict[str, Any], tls: Any) -> None:
    if not isinstance(tls, dict) or not tls:
        return
    if tls.get("enabled") is False:
        return
    proxy["tls"] = True
    sni = tls.get("server_name") or tls.get("sni")
    if sni:
        proxy["sni"] = sni
    if tls.get("insecure") is True:
        proxy["skip-cert-verify"] = True
    alpn = tls.get("alpn")
    if alpn:
        proxy["alpn"] = alpn
    utls = tls.get("utls") if isinstance(tls.get("utls"), dict) else {}
    fp = utls.get("fingerprint") or tls.get("fingerprint")
    if fp:
        proxy["client-fingerprint"] = fp
    reality = tls.get("reality") if isinstance(tls.get("reality"), dict) else {}
    if reality.get("enabled"):
        proxy["reality-opts"] = {
            "public-key": reality.get("public_key") or "",
            "short-id": reality.get("short_id") or "",
        }


def _singbox_transport(proxy: dict[str, Any], transport: Any) -> None:
    if not isinstance(transport, dict):
        return
    net = str(transport.get("type") or "").lower()
    if not net:
        return
    if net == "ws":
        proxy["network"] = "ws"
        headers = transport.get("headers") if isinstance(transport.get("headers"), dict) else {}
        proxy["ws-opts"] = {
            "path": transport.get("path") or "/",
            "headers": {"Host": headers.get("Host") or headers.get("host") or ""},
        }
    elif net == "grpc":
        proxy["network"] = "grpc"
        proxy["grpc-opts"] = {
            "grpc-service-name": transport.get("service_name") or transport.get("servicename") or "",
        }
    elif net in {"http", "h2", "httpupgrade"}:
        proxy["network"] = "http"
        proxy["http-opts"] = {"path": transport.get("path") or "/"}


def convert_singbox_outbound(item: dict[str, Any]) -> dict[str, Any] | None:
    raw_type = str(item.get("type") or "").lower().strip()
    if raw_type in _SINGBOX_SKIP_TYPES or not raw_type:
        return None
    mapped = {
        "shadowsocks": "ss",
        "shadowsocks2022": "ss",
        "hy2": "hysteria2",
        "socks": "socks5",
    }.get(raw_type, raw_type)
    if mapped not in SUPPORTED_PROXY_TYPES:
        return None
    server = item.get("server") or item.get("address")
    port = item.get("server_port") or item.get("port")
    if not server or not port:
        return None
    proxy: dict[str, Any] = {
        "name": str(item.get("tag") or item.get("name") or "singbox"),
        "type": mapped,
        "server": str(server),
        "port": int(port),
    }
    if mapped == "ss":
        method = item.get("method") or item.get("cipher")
        password = item.get("password")
        if method:
            proxy["cipher"] = method
        if password:
            proxy["password"] = password
    elif mapped in {"vmess", "vless"}:
        uuid = item.get("uuid") or item.get("id")
        if uuid:
            proxy["uuid"] = uuid
        if mapped == "vmess":
            proxy["alterId"] = int(item.get("alter_id") or item.get("alterId") or 0)
            proxy["cipher"] = item.get("security") or "auto"
        if mapped == "vless":
            proxy["encryption"] = item.get("encryption") or "none"
            flow = item.get("flow")
            if flow:
                proxy["flow"] = flow
    elif mapped in {"trojan", "hysteria", "hysteria2", "tuic"}:
        password = item.get("password") or item.get("uuid") or item.get("auth_str") or item.get("auth")
        if password:
            if mapped == "hysteria":
                proxy["auth-str"] = password
            else:
                proxy["password"] = password
        if mapped == "hysteria":
            if item.get("up_mbps") or item.get("up"):
                proxy["up"] = item.get("up_mbps") or item.get("up")
            if item.get("down_mbps") or item.get("down"):
                proxy["down"] = item.get("down_mbps") or item.get("down")
        if mapped == "hysteria2" and item.get("obfs"):
            obfs = item["obfs"]
            if isinstance(obfs, dict):
                proxy["obfs"] = obfs.get("type") or "salamander"
                if obfs.get("password"):
                    proxy["obfs-password"] = obfs.get("password")
        if mapped == "tuic":
            if item.get("uuid"):
                proxy["uuid"] = item.get("uuid")
            if item.get("congestion_control"):
                proxy["congestion-controller"] = item.get("congestion_control")
    elif mapped == "wireguard":
        proxy["private-key"] = item.get("private_key") or item.get("private-key") or ""
        peers = item.get("peers") if isinstance(item.get("peers"), list) else []
        peer = peers[0] if peers and isinstance(peers[0], dict) else item
        proxy["public-key"] = peer.get("public_key") or peer.get("public-key") or ""
        if peer.get("allowed_ips"):
            proxy["allowed-ips"] = peer.get("allowed_ips")
        if peer.get("reserved"):
            proxy["reserved"] = peer.get("reserved")
    elif mapped == "socks5":
        if item.get("username"):
            proxy["username"] = item.get("username")
        if item.get("password"):
            proxy["password"] = item.get("password")
    _singbox_tls(proxy, item.get("tls"))
    _singbox_transport(proxy, item.get("transport"))
    return proxy


def extract_singbox_from_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    outbounds = data.get("outbounds")
    items = outbounds if isinstance(outbounds, list) else [data]
    found: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        proxy = convert_singbox_outbound(item)
        if proxy:
            found.append(proxy)
    return found


def extract_singbox_proxies(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for value in _iter_json_values(text):
        if isinstance(value, dict):
            found.extend(extract_singbox_from_data(value))
    return found


def _split_host_port(server: str, default_port: int = 443) -> tuple[str, int] | None:
    text = str(server or "").strip()
    if not text:
        return None
    if text.startswith("["):
        host, _, rest = text[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else str(default_port)
        return host, int(port or default_port)
    if text.count(":") == 1:
        host, port = text.rsplit(":", 1)
        return host, int(port or default_port)
    return text, default_port


def extract_hysteria_client(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "auth_str" not in data or "server" not in data:
        return []
    hp = _split_host_port(str(data.get("server") or ""))
    if not hp:
        return []
    host, port = hp
    proxy: dict[str, Any] = {
        "name": "hysteria",
        "type": "hysteria",
        "server": host,
        "port": port,
        "auth-str": data.get("auth_str") or "",
        "protocol": data.get("protocol") or "udp",
        "up": data.get("up_mbps") or data.get("up"),
        "down": data.get("down_mbps") or data.get("down"),
    }
    if data.get("server_name"):
        proxy["sni"] = data.get("server_name")
    if data.get("insecure") is True:
        proxy["skip-cert-verify"] = True
    if data.get("alpn"):
        proxy["alpn"] = [data.get("alpn")] if isinstance(data.get("alpn"), str) else data.get("alpn")
    if data.get("obfs"):
        proxy["obfs"] = data.get("obfs")
    return [proxy]


def extract_hysteria2_client(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "outbounds" in data or "auth_str" in data:
        return []
    if "auth" not in data or "server" not in data:
        return []
    hp = _split_host_port(str(data.get("server") or ""))
    if not hp:
        return []
    host, port = hp
    tls = data.get("tls") if isinstance(data.get("tls"), dict) else {}
    bw = data.get("bandwidth") if isinstance(data.get("bandwidth"), dict) else {}
    proxy: dict[str, Any] = {
        "name": "hysteria2",
        "type": "hysteria2",
        "server": host,
        "port": port,
        "password": data.get("auth") or "",
    }
    if tls.get("sni"):
        proxy["sni"] = tls.get("sni")
    if tls.get("insecure") is True:
        proxy["skip-cert-verify"] = True
    if bw.get("up"):
        proxy["up"] = bw.get("up")
    if bw.get("down"):
        proxy["down"] = bw.get("down")
    return [proxy]


def extract_xray_proxies(data: dict[str, Any]) -> list[dict[str, Any]]:
    outbounds = data.get("outbounds")
    if not isinstance(outbounds, list):
        return []
    found: list[dict[str, Any]] = []
    for item in outbounds:
        if not isinstance(item, dict):
            continue
        protocol = str(item.get("protocol") or item.get("type") or "").lower()
        if protocol in {"freedom", "blackhole", "dns", "direct", "block"}:
            continue
        settings = item.get("settings") if isinstance(item.get("settings"), dict) else {}
        stream = item.get("streamSettings") if isinstance(item.get("streamSettings"), dict) else {}
        server = ""
        port = 0
        uuid = ""
        password = ""
        method = ""
        vnext = settings.get("vnext") if isinstance(settings.get("vnext"), list) else []
        servers = settings.get("servers") if isinstance(settings.get("servers"), list) else []
        if vnext and isinstance(vnext[0], dict):
            node = vnext[0]
            server = str(node.get("address") or "")
            port = int(node.get("port") or 0)
            users = node.get("users") if isinstance(node.get("users"), list) else []
            if users and isinstance(users[0], dict):
                uuid = str(users[0].get("id") or "")
                password = str(users[0].get("password") or "")
                method = str(users[0].get("encryption") or users[0].get("security") or "")
        elif servers and isinstance(servers[0], dict):
            node = servers[0]
            server = str(node.get("address") or "")
            port = int(node.get("port") or 0)
            uuid = str(node.get("id") or "")
            password = str(node.get("password") or "")
            method = str(node.get("method") or "")
        if not server or not port:
            continue
        mapped = {"shadowsocks": "ss", "socks": "socks5"}.get(protocol, protocol)
        if mapped not in SUPPORTED_PROXY_TYPES:
            continue
        proxy: dict[str, Any] = {
            "name": str(item.get("tag") or mapped),
            "type": mapped,
            "server": server,
            "port": port,
        }
        if mapped in {"vmess", "vless"} and uuid:
            proxy["uuid"] = uuid
            if mapped == "vless":
                proxy["encryption"] = method or "none"
            if mapped == "vmess":
                proxy["alterId"] = 0
                proxy["cipher"] = method or "auto"
        elif mapped in {"trojan", "ss"} and (password or uuid):
            proxy["password"] = password or uuid
            if mapped == "ss" and method:
                proxy["cipher"] = method
        net = str(stream.get("network") or "tcp").lower()
        if net in {"ws", "grpc", "http", "h2"}:
            proxy["network"] = "http" if net == "h2" else net
            if net == "ws":
                ws = stream.get("wsSettings") if isinstance(stream.get("wsSettings"), dict) else {}
                headers = ws.get("headers") if isinstance(ws.get("headers"), dict) else {}
                proxy["ws-opts"] = {"path": ws.get("path") or "/", "headers": {"Host": headers.get("Host") or ""}}
            if net == "grpc":
                grpc = stream.get("grpcSettings") if isinstance(stream.get("grpcSettings"), dict) else {}
                proxy["grpc-opts"] = {"grpc-service-name": grpc.get("serviceName") or ""}
        security = str(stream.get("security") or "").lower()
        if security in {"tls", "reality"}:
            proxy["tls"] = True
            tls = stream.get("tlsSettings") if isinstance(stream.get("tlsSettings"), dict) else {}
            reality = stream.get("realitySettings") if isinstance(stream.get("realitySettings"), dict) else {}
            sni = tls.get("serverName") or reality.get("serverName")
            if sni:
                proxy["sni"] = sni
            if tls.get("allowInsecure") is True:
                proxy["skip-cert-verify"] = True
            if security == "reality":
                proxy["reality-opts"] = {
                    "public-key": reality.get("publicKey") or "",
                    "short-id": (reality.get("shortId") or ""),
                }
        found.append(proxy)
    return found


def _iter_json_values(text: str, nested: bool = False) -> list[Any]:
    stripped = str(text or "").strip()
    if not stripped:
        return []
    if not nested:
        try:
            return [json.loads(stripped)]
        except Exception:
            pass
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    length = len(stripped)
    while index < length:
        while index < length and stripped[index] not in "{[":
            index += 1
        if index >= length:
            break
        try:
            value, end = decoder.raw_decode(stripped, index)
        except Exception:
            index += 1
            continue
        values.append(value)
        index = (index + 1) if nested else max(end, index + 1)
    return values


def _proxies_from_json_value(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        found: list[dict[str, Any]] = []
        for item in data:
            found.extend(_proxies_from_json_value(item))
        return found
    if not isinstance(data, dict):
        return []
    proxies = data.get("proxies")
    if isinstance(proxies, list) and proxies:
        return [item for item in proxies if isinstance(item, dict)]
    if data.get("protocol") and isinstance(data.get("settings"), dict):
        from_xray = extract_xray_proxies({"outbounds": [data]})
        if from_xray:
            return from_xray
    for extracted in (
        extract_singbox_from_data(data),
        extract_xray_proxies(data),
        extract_hysteria_client(data),
        extract_hysteria2_client(data),
    ):
        if extracted:
            return extracted
    return []


def extract_client_json_proxies(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for value in _iter_json_values(text):
        found.extend(_proxies_from_json_value(value))
    if found:
        return found
    for value in _iter_json_values(text, nested=True):
        found.extend(_proxies_from_json_value(value))
    return found


def extract_proxies(text: str) -> list[dict[str, Any]]:
    decoded = maybe_base64_decode(text)
    stripped = decoded.strip()
    proxies: list[Any] = []
    if stripped.startswith("{") or stripped.startswith("["):
        proxies = extract_client_json_proxies(decoded)
    else:
        share_uris = extract_share_uris(decoded)
        if share_uris and "proxies:" not in decoded:
            clean = []
            for uri in share_uris:
                parsed = parse_share_uri(uri)
                if parsed:
                    clean.append(parsed)
            return clean
        document = load_yaml_document(decoded)
        if isinstance(document, dict):
            proxies = document.get("proxies", [])
        elif isinstance(document, list):
            proxies = document
        else:
            proxies = []
        if not proxies:
            proxies = extract_proxy_block(decoded)

    clean: list[dict[str, Any]] = []
    for proxy in proxies:
        if isinstance(proxy, dict):
            clean.append(dict(proxy))
    for uri in extract_share_uris(decoded):
        parsed = parse_share_uri(uri)
        if parsed:
            clean.append(parsed)
    return clean


def parse_share_uri(uri: str) -> dict[str, Any] | None:
    raw = uri.strip().rstrip(",;")
    scheme = raw.split("://", 1)[0].lower()
    try:
        if scheme == "vmess":
            return _parse_vmess_uri(raw)
        if scheme == "ss":
            return _parse_ss_uri(raw)
        if scheme == "ssr":
            return _parse_ssr_uri(raw)
        if scheme == "tuic":
            return _parse_tuic_uri(raw)
        if scheme in {"socks", "socks5", "socks5h"}:
            return _parse_userhost_uri(raw, "socks5")
        if scheme in {"http", "https"}:
            parsed = _parse_userhost_uri(raw, scheme)
            if parsed and (parsed.get("username") or parsed.get("password")):
                return parsed
            return None
        if scheme in {"wireguard", "wg"}:
            return _parse_wireguard_uri(raw)
        if scheme in {"vless", "trojan", "hysteria", "hysteria2", "hy2"}:
            return _parse_standard_uri(raw, scheme)
    except Exception:
        return None
    return None


def _b64url_decode(payload: str) -> str:
    text = payload.strip().replace("-", "+").replace("_", "/")
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.b64decode(text + pad).decode("utf-8", errors="replace")


def _parse_ssr_uri(uri: str) -> dict[str, Any] | None:
    payload = uri.split("://", 1)[1].split("#", 1)[0]
    decoded = _b64url_decode(payload)
    main, _, query = decoded.partition("/?")
    if "?" in decoded and not query:
        main, _, query = decoded.partition("?")
    parts = main.split(":")
    if len(parts) < 6:
        return None
    host, port, protocol, method, obfs = parts[0], parts[1], parts[2], parts[3], parts[4]
    password = _b64url_decode(":".join(parts[5:]))
    params = {k.lower(): v[0] for k, v in parse_qs(query).items() if v}

    def _param_text(key: str) -> str:
        raw_val = params.get(key, "")
        if not raw_val:
            return ""
        try:
            return _b64url_decode(raw_val)
        except Exception:
            return unquote(raw_val)

    name = _param_text("remarks") or _fragment_name(uri, "ssr")
    proxy: dict[str, Any] = {
        "name": name,
        "type": "ssr",
        "server": host,
        "port": int(port),
        "cipher": method,
        "password": password,
        "protocol": protocol,
        "obfs": obfs,
    }
    proto_param = _param_text("protoparam")
    obfs_param = _param_text("obfsparam")
    if proto_param:
        proxy["protocol-param"] = proto_param
    if obfs_param:
        proxy["obfs-param"] = obfs_param
    return proxy


def _parse_tuic_uri(uri: str) -> dict[str, Any] | None:
    name = _fragment_name(uri, "tuic")
    parsed = urlparse(uri.split("#", 1)[0])
    if not parsed.hostname:
        return None
    qs = {k.lower(): v[0] for k, v in parse_qs(parsed.query).items() if v}
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if parsed.password is None and ":" in user:
        user, password = user.split(":", 1)
    uuid = qs.get("uuid") or user
    secret = password or qs.get("password") or ""
    if not uuid:
        return None
    proxy: dict[str, Any] = {
        "name": name,
        "type": "tuic",
        "server": parsed.hostname,
        "port": int(parsed.port or 443),
        "uuid": uuid,
        "password": secret,
        "udp": True,
    }
    sni = qs.get("sni") or qs.get("peer") or ""
    if sni:
        proxy["sni"] = sni
    cc = qs.get("congestion_control") or qs.get("congestion-control")
    if cc:
        proxy["congestion-controller"] = cc
    mode = qs.get("udp_relay_mode") or qs.get("udp-relay-mode")
    if mode:
        proxy["udp-relay-mode"] = mode
    if qs.get("alpn"):
        proxy["alpn"] = [item.strip() for item in qs["alpn"].split(",") if item.strip()]
    if qs.get("allowinsecure") in {"1", "true"} or qs.get("insecure") in {"1", "true"}:
        proxy["skip-cert-verify"] = True
    return proxy


def _parse_userhost_uri(uri: str, scheme: str) -> dict[str, Any] | None:
    name = _fragment_name(uri, scheme)
    parsed = urlparse(uri.split("#", 1)[0])
    if not parsed.hostname:
        return None
    proxy_type = "http" if scheme in {"http", "https"} else "socks5"
    default_port = 443 if scheme == "https" else 80 if scheme == "http" else 1080
    proxy: dict[str, Any] = {
        "name": name,
        "type": proxy_type,
        "server": parsed.hostname,
        "port": int(parsed.port or default_port),
    }
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    if scheme == "https":
        proxy["tls"] = True
    return proxy


def _fragment_name(uri: str, fallback: str) -> str:
    if "#" in uri:
        return unquote(uri.split("#", 1)[1]).strip() or fallback
    return fallback


def _parse_vmess_uri(uri: str) -> dict[str, Any] | None:
    payload = uri.split("://", 1)[1].split("#", 1)[0]
    pad = "=" * ((4 - len(payload) % 4) % 4)
    data = json.loads(base64.b64decode(payload + pad).decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        return None
    name = str(data.get("ps") or _fragment_name(uri, "vmess")).strip()
    proxy: dict[str, Any] = {
        "name": name,
        "type": "vmess",
        "server": str(data.get("add", "")).strip(),
        "port": int(data.get("port", 0)),
        "uuid": str(data.get("id", "")).strip(),
        "alterId": int(data.get("aid") or 0),
        "cipher": str(data.get("scy") or "auto"),
        "network": str(data.get("net") or "tcp"),
        "tls": str(data.get("tls") or "").lower() in {"tls", "true", "1"},
        "udp": True,
    }
    host = str(data.get("host") or "").strip()
    path = str(data.get("path") or "/").strip() or "/"
    sni = str(data.get("sni") or host).strip()
    if proxy["tls"] and sni:
        proxy["servername"] = sni
    if data.get("fp"):
        proxy["client-fingerprint"] = str(data.get("fp"))
    if proxy["network"] == "ws":
        proxy["ws-opts"] = {"path": path, "headers": {"Host": host or proxy["server"]}}
    elif proxy["network"] == "grpc":
        proxy["grpc-opts"] = {"grpc-service-name": path.lstrip("/")}
    return proxy


def _parse_ss_uri(uri: str) -> dict[str, Any] | None:
    rest = uri.split("://", 1)[1]
    name = _fragment_name(uri, "ss")
    main = rest.split("#", 1)[0]
    plugin = ""
    if "/?" in main:
        main, plugin = main.split("/?", 1)
    elif "?" in main:
        main, plugin = main.split("?", 1)
    if "@" not in main:
        pad = "=" * ((4 - len(main) % 4) % 4)
        main = base64.b64decode(main + pad).decode("utf-8", errors="replace")
    userinfo, hostport = main.rsplit("@", 1)
    if ":" not in userinfo:
        pad = "=" * ((4 - len(userinfo) % 4) % 4)
        userinfo = base64.b64decode(userinfo + pad).decode("utf-8", errors="replace")
    method, password = userinfo.split(":", 1)
    host, port = hostport.rsplit(":", 1)
    proxy: dict[str, Any] = {
        "name": name,
        "type": "ss",
        "server": unquote(host),
        "port": int(port),
        "cipher": unquote(method),
        "password": unquote(password),
        "udp": True,
    }
    if plugin:
        qs = parse_qs(plugin)
        if qs.get("plugin"):
            proxy["plugin"] = qs["plugin"][0]
    return proxy


def _parse_wireguard_uri(uri: str) -> dict[str, Any] | None:
    name = _fragment_name(uri, "wireguard")
    parsed = urlparse(uri.split("#", 1)[0])
    qs = {k.lower().replace("_", "-"): v[0] for k, v in parse_qs(parsed.query).items() if v}
    private_key = unquote(parsed.username or "") or qs.get("privatekey") or qs.get("private-key") or ""
    public_key = qs.get("publickey") or qs.get("public-key") or qs.get("peer-public-key") or ""
    host = parsed.hostname or qs.get("server") or qs.get("endpoint") or ""
    port = parsed.port or qs.get("port") or 51820
    if not private_key or not host:
        return None
    try:
        port = int(port)
    except Exception:
        return None
    proxy: dict[str, Any] = {
        "name": name,
        "type": "wireguard",
        "server": host,
        "port": port,
        "private-key": private_key,
        "udp": True,
    }
    if public_key:
        proxy["public-key"] = public_key
    address = qs.get("address") or qs.get("ip") or ""
    if address:
        first = address.split(",")[0].split("/")[0].strip()
        if ":" in first:
            proxy["ipv6"] = first
        elif first:
            proxy["ip"] = first
    if qs.get("ipv6"):
        proxy["ipv6"] = qs["ipv6"].split("/")[0].strip()
    if qs.get("dns"):
        proxy["dns"] = [item.strip() for item in qs["dns"].split(",") if item.strip()]
    if qs.get("mtu"):
        try:
            proxy["mtu"] = int(qs["mtu"])
        except Exception:
            pass
    reserved = qs.get("reserved") or ""
    if reserved:
        if "," in reserved:
            try:
                proxy["reserved"] = [int(item.strip()) for item in reserved.split(",") if item.strip()]
            except Exception:
                proxy["reserved"] = reserved
        else:
            proxy["reserved"] = reserved
    psk = qs.get("presharedkey") or qs.get("preshared-key") or ""
    if psk:
        proxy["preshared-key"] = psk
    return proxy


def _parse_standard_uri(uri: str, scheme: str) -> dict[str, Any] | None:
    name = _fragment_name(uri, scheme)
    main = uri.split("#", 1)[0]
    parsed = urlparse(main)
    if not parsed.hostname or not parsed.port:
        return None
    user = unquote(parsed.username or "")
    qs = {k.lower(): v[0] for k, v in parse_qs(parsed.query).items() if v}
    net = (qs.get("type") or qs.get("network") or "tcp").lower()
    security = (qs.get("security") or "").lower()
    proxy_type = "hysteria2" if scheme in {"hy2", "hysteria2"} else scheme
    proxy: dict[str, Any] = {
        "name": name,
        "type": proxy_type,
        "server": parsed.hostname,
        "port": int(parsed.port),
        "udp": True,
    }
    if proxy_type == "vless":
        proxy["uuid"] = user
        proxy["encryption"] = qs.get("encryption") or "none"
        if qs.get("flow"):
            proxy["flow"] = qs["flow"]
    elif proxy_type == "trojan":
        proxy["password"] = user
    else:
        proxy["password"] = user

    tls = security in {"tls", "reality"} or qs.get("sni") or proxy_type in {"trojan", "hysteria2"}
    if tls:
        proxy["tls"] = True
    sni = qs.get("sni") or qs.get("servername") or qs.get("host") or ""
    if sni:
        proxy["servername"] = sni
        if proxy_type == "trojan":
            proxy["sni"] = sni
    if qs.get("fp"):
        proxy["client-fingerprint"] = qs["fp"]
    if qs.get("insecure") in {"1", "true"} or qs.get("allowinsecure") in {"1", "true"}:
        proxy["skip-cert-verify"] = True
    if security == "reality":
        proxy["tls"] = True
        reality: dict[str, Any] = {}
        if qs.get("pbk"):
            reality["public-key"] = qs["pbk"]
        if qs.get("sid"):
            reality["short-id"] = qs["sid"]
        if reality:
            proxy["reality-opts"] = reality

    proxy["network"] = net
    path = qs.get("path") or "/"
    host = qs.get("host") or sni or parsed.hostname
    if net == "ws":
        proxy["ws-opts"] = {"path": path, "headers": {"Host": host}}
    elif net == "grpc":
        proxy["grpc-opts"] = {"grpc-service-name": (qs.get("servicename") or path).lstrip("/")}
    return proxy


def collect_proxies() -> tuple[int, list[dict[str, Any]], dict[str, int]]:
    global _SEP_JUST_PRINTED
    collected: list[dict[str, Any]] = []
    first = True
    for source in SOURCE_GROUPS:
        if not first:
            _SEP_JUST_PRINTED = False
            print_sep()
        first = False
        source_found: list[dict[str, Any]] = []
        used_url = ""
        for item in _source_queue(source):
            if source_found:
                break
            url, prefer, exclude = _item_spec(item, source)
            merge_all = False
            if url.startswith("discover:article:"):
                candidates = discover_article(url[len("discover:article:"):], prefer=prefer)
            elif url.startswith("discover:sublink:"):
                candidates = discover_sublink(
                    url[len("discover:sublink:"):],
                    prefer=prefer,
                    exclude=exclude,
                )
            elif url.startswith("discover:toolkit:"):
                candidates = discover_toolkit(url[len("discover:toolkit:"):], prefer=prefer)
                merge_all = True
            else:
                candidates = [url]
            toolkit_hits: list[tuple[str, int]] = []
            if merge_all and _TOOLKIT_EMBEDDED:
                prefix = source.get("prefix", "")
                local_nodes = []
                for proxy in _TOOLKIT_EMBEDDED:
                    item = dict(proxy)
                    if prefix:
                        item["name"] = prefix + str(item.get("name", "")).strip()
                    local_nodes.append(item)
                source_found.extend(local_nodes)
                toolkit_hits.append(("embedded://archive-config", len(local_nodes)))
            for url in unique_ordered(candidates):
                try:
                    text = fetch_text(
                        url,
                        user_agent=str(source.get("user_agent") or ""),
                        referer=str(source.get("referer") or ""),
                    )
                    head = str(text).lstrip()[:64].lower()
                    if merge_all and head.startswith(("<!", "<html", "<head", "<title")):
                        continue
                    found = extract_proxies(text)
                    if found:
                        prefix = source.get("prefix", "")
                        if prefix:
                            for p in found:
                                if isinstance(p, dict):
                                    p["name"] = prefix + str(p.get("name", "")).strip()
                        source_found.extend(found)
                        used_url = url
                        if merge_all:
                            toolkit_hits.append((url, len(found)))
                            continue
                        break
                    if not merge_all:
                        print(f"[WARN] source={source['name']} empty url={url}")
                except Exception as exc:
                    if not merge_all:
                        print(f"[WARN] source={source['name']} skipped url={url} error={exc}")
                if source_found and not merge_all:
                    break
        if not source_found:
            print(f"[WARN] source={source['name']} no proxies")
            source_found = load_previous_source_proxies(source)
        elif merge_all:
            _print_toolkit_groups(toolkit_hits)
            print(f"[OK] proxies={len(source_found)} source={source['name']}")
        elif used_url:
            print(f"[OK] proxies={len(source_found)} source={source['name']} url={used_url}")
        collected.extend(source_found)

    write_raw_backup(collected)
    sanitized = sanitize_and_deduplicate(collected)
    if MAX_CANDIDATES > 0 and len(sanitized) > MAX_CANDIDATES:
        print(f"[WARN] limiting candidates from {len(sanitized)} to {MAX_CANDIDATES}")
        sanitized = sanitized[:MAX_CANDIDATES]
    collected_counts: dict[str, int] = {}
    for proxy in collected:
        if not isinstance(proxy, dict):
            continue
        key = source_prefix_of(str(proxy.get("name") or ""))
        collected_counts[key] = collected_counts.get(key, 0) + 1
    return len(collected), sanitized, collected_counts


def _source_queue(source: dict[str, Any]) -> list[Any]:
    items = [source["primary"]]
    items.extend(source.get("fallbacks", []))
    return items


def _item_spec(item: Any, source: dict[str, Any]) -> tuple[str, str, str]:
    if isinstance(item, dict):
        url = str(item.get("url") or "")
        prefer = str(item["prefer"]) if "prefer" in item else str(source.get("prefer") or "")
        exclude = str(item["exclude"]) if "exclude" in item else str(source.get("exclude") or "")
        return url, prefer, exclude
    return str(item), str(source.get("prefer") or ""), str(source.get("exclude") or "")


def _blob_to_raw(link: str) -> str:
    blob = re.search(
        r"github\.com/([^/]+)/([^/]+)/(?:blob|tree)/([^/]+)/(.+)",
        link,
        re.IGNORECASE,
    )
    if blob:
        owner, repo, ref, path = blob.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    return link


def _probe_sub_file(tag: str, link: str) -> bool:
    link = _blob_to_raw(link.strip())
    print(f"[INFO] {tag} try file: {link}")
    try:
        body = fetch_text(link)
    except Exception as exc:
        print(f"[WARN] {tag} fetch failed: {link} {exc}")
        return False
    if not str(body).strip():
        print(f"[WARN] {tag} empty file: {link}")
        return False
    found = extract_proxies(body)
    if not found:
        print(f"[WARN] {tag} empty subscription: {link}")
        return False
    return True


def _score_sub_link(url: str, context: str = "", prefer: str = "", distance: int = 9999) -> int:
    blob = f"{url} {context}".lower()
    path = url.split("?", 1)[0].lower()
    filename = path.rstrip("/").rsplit("/", 1)[-1]
    score = 1
    hint = prefer.strip().lower()
    if hint and hint in blob:
        score += 4000
    if hint and distance < 400:
        score += max(0, 8000 - distance * 10)
    stamp = ""
    found = re.search(r"(20\d{6})", filename) or re.search(r"(20\d{6})", path)
    if found:
        stamp = found.group(1)
    else:
        found = re.search(r"(20\d{2})[/_-](\d{1,2})[/_-](\d{1,2})", path)
        if found:
            stamp = f"{found.group(1)}{int(found.group(2)):02d}{int(found.group(3)):02d}"
    if stamp:
        try:
            day = datetime.strptime(stamp, "%Y%m%d").replace(tzinfo=timezone.utc)
            if day >= datetime.now(timezone.utc) - timedelta(days=10):
                score += int(stamp) * 1000
        except ValueError:
            pass
    if filename.endswith(".txt"):
        score += 500
    if filename.endswith(".json"):
        score += 340
    if filename.endswith((".yaml", ".yml")):
        score += 300
    if "mihomo" in filename or re.fullmatch(r"m20\d{6}\.ya?ml", filename):
        score += 80
    if re.search(r"clash-?meta", filename):
        score += 200
    if "v2ray" in filename and "clash" not in filename and not filename.endswith((".yaml", ".yml")):
        score += 500
    return score


def _collect_sub_links(text: str, page_url: str = "", prefer: str = "", exclude: str = "") -> list[str]:
    text = html.unescape(text or "")
    files: list[tuple[int, str]] = []
    bare: list[tuple[int, str]] = []
    file_re = re.compile(r"\.(?:yaml|yml|txt|json)(?:$|[?#])", re.I)
    skip_re = re.compile(
        r"(github\.com|youtube\.com|youtu\.be|karing\.app|"
        r"t\.me/|telegram\.(?:me|org)|api\.w\.org|clarity\.ms|v2ray\.com|"
        r"\.(?:html?|png|jpe?g|gif|svg|webp|js|css|zip|exe|dmg|apk)(?:$|[?#&]))",
        re.I,
    )
    exclude_keyword = exclude.strip().lower()
    hint = prefer.strip().lower()
    prefer_positions = []
    if hint:
        lower_text = text.lower()
        start = 0
        while True:
            pos = lower_text.find(hint, start)
            if pos == -1:
                break
            prefer_positions.append(pos)
            start = pos + len(hint)
    for match in re.finditer(r"https?://[^\s\"'<>\]\)]+", text, re.I):
        raw = match.group(0).split("`")[0].rstrip(").,;\"'")
        link = _blob_to_raw(raw)
        if exclude_keyword and exclude_keyword in link.lower():
            continue
        url_start = match.start()
        min_distance = 9999
        if prefer_positions:
            min_distance = min(abs(url_start - pos) for pos in prefer_positions)
        scored = _score_sub_link(link, match.group(0), prefer=prefer, distance=min_distance)
        if file_re.search(link):
            files.append((scored, link))
        elif skip_re.search(link):
            continue
        else:
            bare.append((scored, link))
    if prefer_positions:
        chosen = files + bare
    else:
        chosen = files if files else bare
    chosen.sort(key=lambda item: item[0], reverse=True)
    return unique_ordered([url for _, url in chosen])


def discover_sublink(page_url: str, prefer: str = "", exclude: str = "") -> list[str]:
    page_url = _blob_to_raw(page_url.strip())
    print(f"[INFO] sublink try page: {page_url}")
    try:
        body = fetch_text(page_url)
    except Exception as exc:
        print(f"[WARN] sublink page failed: {page_url} {exc}")
        return []
    candidate_links = _collect_sub_links(body, page_url, prefer=prefer, exclude=exclude)
    for link in candidate_links:
        if _probe_sub_file("sublink", link):
            return [link]
    print(f"[WARN] sublink discovery failed: {page_url}")
    return []


def _collect_article_links(text: str, page_url: str) -> list[str]:
    text = html.unescape(text or "")
    found: list[str] = []
    for match in re.finditer(r"https?://[^\s\"'<>\]]+|href=[\"']([^\"']+)[\"']", text, re.I):
        link = match.group(1) or match.group(0)
        if link.lower().startswith("href="):
            continue
        if link.startswith("/"):
            from urllib.parse import urljoin
            link = urljoin(page_url, link)
        if not link.startswith("http"):
            continue
        if re.search(r"\.(?:yaml|yml|txt|json|apk|exe|dmg|zip|png|jpe?g|gif|svg|webp|js|css)(?:$|[?#])", link, re.I):
            continue
        if re.search(r"/fn/\d{8}|/post/|/p/\d+", link) or link.endswith(".html"):
            found.append(link)
    return unique_ordered(found)


def _page_stamp(text: str) -> str:
    match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
    if match:
        return f"{match.group(1)}{int(match.group(2)):02d}{int(match.group(3)):02d}"
    match = re.search(r"(20\d{6})", text)
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})[/_-](\d{1,2})[/_-](\d{1,2})", text)
    if match:
        return f"{match.group(1)}{int(match.group(2)):02d}{int(match.group(3)):02d}"
    return "00000000"


_ARCHIVE_EXT_RE = re.compile(
    r"\.(?:7z|zip|rar|tar\.gz|tgz|tar)(?:$|[?#).,;\"'])",
    re.I,
)
_ANDROID_PKG_RE = re.compile(
    r"\.(?:apk|xapk|apks|aab)(?:$|[?#).,;\"'])",
    re.I,
)
_BROWSER_PKG_RE = re.compile(
    r"\.(?:crx|xpi|nex)(?:$|[?#).,;\"'])",
    re.I,
)
_INSTALLER_EXT_RE = re.compile(
    r"\.(?:apk|xapk|apks|aab|crx|xpi|nex|exe|msi|msix|appx|"
    r"dmg|pkg|deb|rpm|ipa|cab)(?:$|[?#).,;\"'])",
    re.I,
)
_TOOLKIT_SKIP_HOST_RE = re.compile(
    r"7-zip\.org|sourceforge\.net/projects/sevenzip|microsoft\.com|aka\.ms|"
    r"apps\.apple\.com|itunes\.apple\.com|"
    r"(?:^|//)(?:www\.)?(?:t\.me|telegram\.(?:me|org)|youtube\.com|youtu\.be)/",
    re.I,
)
_TOOLKIT_TEXT_EXT = {
    ".bat", ".cmd", ".ps1", ".psm1",
    ".sh", ".bash", ".zsh", ".fish", ".command",
    ".txt", ".url", ".md", ".ini", ".conf", ".cfg", ".config",
    ".yaml", ".yml", ".json", ".toml", ".xml", ".plist",
    ".list", ".sub", ".csv",
}
_TOOLKIT_CONFIG_EXT = {
    ".yaml", ".yml", ".json", ".txt", ".md",
    ".conf", ".cfg", ".list", ".sub",
}
_TOOLKIT_EMBEDDED: list[dict[str, Any]] = []


def _clean_found_url(link: str, page_url: str) -> str:
    from urllib.parse import urljoin
    link = html.unescape(str(link or "")).strip()
    if link.lower().startswith("href="):
        return ""
    if link.startswith("/"):
        link = urljoin(page_url, link)
    link = link.split("#")[0].rstrip("\\").rstrip(").,;\"']")
    if not link.startswith("http"):
        return ""
    if _TOOLKIT_SKIP_HOST_RE.search(link):
        return ""
    return link


def _collect_archive_links(text: str, page_url: str) -> list[str]:
    text = html.unescape(text or "")
    found: list[str] = []
    patterns = (
        r"\[[^\]]*\]\((https?://[^)\s]+)\)",
        r"href=[\"']([^\"']+)[\"']",
        r"https?://[^\s\"'<>]+",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            raw = match.group(1) if match.lastindex else match.group(0)
            link = _clean_found_url(raw, page_url)
            if not link:
                continue
            if (
                _ARCHIVE_EXT_RE.search(link)
                or _INSTALLER_EXT_RE.search(link)
                or re.search(r"github\.com/.+/releases(?:/|$)", link, re.I)
            ):
                found.append(link)
    return unique_ordered(found)


def _package_score(link: str, prefer: str = "") -> int:
    lower = str(link or "").lower()
    score = 0
    if _ARCHIVE_EXT_RE.search(lower):
        score = 80
    elif _ANDROID_PKG_RE.search(lower):
        score = 70
    elif _BROWSER_PKG_RE.search(lower):
        score = 65
    elif _INSTALLER_EXT_RE.search(lower):
        score = 25
    elif re.search(r"github\.com/.+/releases(?:/|$)", lower):
        score = 40
    if not score:
        return 0
    token = (prefer or "").strip().lower()
    if token and token in lower:
        score += 20
    return score


def _rank_package_links(links: list[str], prefer: str = "") -> list[str]:
    ranked = [( _package_score(link, prefer), link) for link in links]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(key=lambda item: item[0], reverse=True)
    return unique_ordered([url for _, url in ranked])


def _toolkit_kind(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "chromewebstore.google.com" in host or "chrome.google.com" in host:
        return "chrome"
    if "microsoftedge.microsoft.com" in host:
        return "edge"
    if "addons.mozilla.org" in host:
        return "firefox"
    if re.search(r"github\.com/[^/]+/[^/]+", url, re.I) and "/releases" in path and "/releases/download/" not in path:
        return "release"
    return "probe"


def _payload_is_binary(sample: bytes, content_type: str) -> bool:
    ct = (content_type or "").lower()
    head = sample.lstrip()[:256].lower()
    if any(token in ct for token in ("text/", "html", "xml", "json", "javascript")):
        return False
    if head.startswith((b"<!doctype", b"<html", b"<?xml", b"<rss", b"<feed", b"{", b"[")):
        return False
    if sample.startswith((b"PK\x03\x04", b"7z\xbc\xaf", b"Rar!", b"Cr24", b"\x1f\x8b")):
        return True
    if "octet-stream" in ct or "zip" in ct or "7z" in ct or "compressed" in ct:
        return True
    if b"\x00" in sample[:512]:
        return True
    return False


def _probe_payload(url: str) -> str:
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    proxy_tries = [PROXIES, {}] if PROXIES else [{}]
    for proxies in proxy_tries:
        try:
            with session.get(
                url,
                headers={"User-Agent": resolve_ua("Chrome")},
                timeout=SOURCE_TIMEOUT,
                stream=True,
                verify=False,
                proxies=proxies,
            ) as response:
                response.raise_for_status()
                sample = next(response.iter_content(chunk_size=4096), b"") or b""
                if _payload_is_binary(sample, response.headers.get("Content-Type", "")):
                    return "direct"
                return "page"
        except Exception:
            continue
    return "page"


def _chrome_ext_id(url: str) -> str:
    match = re.search(
        r"(?:chromewebstore\.google\.com|chrome\.google\.com/webstore)/detail(?:/[^/]+)?/([a-p]{32})",
        url,
        re.I,
    )
    return match.group(1) if match else ""


def _edge_ext_id(url: str) -> str:
    match = re.search(r"microsoftedge\.microsoft\.com/addons/detail(?:/[^/]+)?/([a-z0-9]+)", url, re.I)
    return match.group(1) if match else ""


def _firefox_slug(url: str) -> str:
    match = re.search(r"addons\.mozilla\.org/[^/]+/firefox/addon/([^/?#]+)", url, re.I)
    return unquote(match.group(1)).strip("/") if match else ""


def _store_package_urls(kind: str, page_url: str) -> list[str]:
    if kind == "chrome":
        ext_id = _chrome_ext_id(page_url)
        if not ext_id:
            return []
        return [
            (
                "https://clients2.google.com/service/update2/crx"
                "?response=redirect&prodversion=131.0.6778.0"
                f"&acceptformat=crx2,crx3&x=id%3d{ext_id}%26uc"
            )
        ]
    if kind == "edge":
        ext_id = _edge_ext_id(page_url)
        if not ext_id:
            return []
        return [
            (
                "https://edge.microsoft.com/extensionwebstorebase/v1/crx"
                f"?response=redirect&x=id%3d{ext_id}%26installsource%3dondemand%26uc"
            )
        ]
    if kind == "firefox":
        slug = _firefox_slug(page_url)
        if not slug:
            return []
        return [
            f"https://addons.mozilla.org/firefox/downloads/latest/{slug}/addon-{slug}-latest.xpi",
            f"https://addons.mozilla.org/firefox/downloads/file/latest/{slug}.xpi",
        ]
    return []


def _expand_github_release_assets(page_url: str, prefer: str = "") -> list[str]:
    match = re.search(r"github\.com/([^/]+)/([^/]+)", page_url, re.I)
    if not match:
        return []
    owner, repo = match.group(1), match.group(2)
    token = (prefer or "").strip().lower()
    list_url = f"https://github.com/{owner}/{repo}/releases"
    if list_url.rstrip("/") != page_url.rstrip("/"):
        print(f"[INFO] toolkit try page: {list_url}")
    try:
        listing = fetch_text(list_url)
    except Exception as exc:
        print(f"[WARN] toolkit page failed: {list_url} {exc}")
        listing = ""
    tags: list[tuple[int, str]] = []
    seen_tags: set[str] = set()
    tag_match = re.search(r"/releases/tag/([^/?#\"']+)", page_url, re.I)
    if tag_match:
        tags.append((9, unquote(tag_match.group(1))))
        seen_tags.add(tag_match.group(1))
    for found in re.finditer(r"/releases/tag/([^/?#\"']+)", listing, re.I):
        tag = unquote(found.group(1))
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        score = 5 if token and token.lower() in tag.lower() else 1
        tags.append((score, tag))
    if "latest" not in seen_tags:
        tags.append((4 if token else 1, "latest"))
    tags.sort(key=lambda item: item[0], reverse=True)
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for _, tag in tags:
        asset_page = f"https://github.com/{owner}/{repo}/releases/expanded_assets/{tag}"
        print(f"[INFO] toolkit try page: {asset_page}")
        try:
            body = fetch_text(asset_page)
        except Exception as exc:
            print(f"[WARN] toolkit page failed: {asset_page} {exc}")
            continue
        for link in _collect_archive_links(body, asset_page):
            lower = link.lower()
            if "/releases/download/" not in lower:
                continue
            if not (_ARCHIVE_EXT_RE.search(link) or _INSTALLER_EXT_RE.search(link)):
                continue
            if link in seen:
                continue
            seen.add(link)
            score = 3 if token and token in lower else 1
            ranked.append((score, link))
        if ranked:
            break
    ranked.sort(key=lambda item: item[0], reverse=True)
    return unique_ordered([url for _, url in ranked])


def _download_archive(url: str, dest_dir: Path) -> Path | None:
    from urllib.parse import urlparse, unquote
    name = unquote(Path(urlparse(url).path).name) or "toolkit.bin"
    if not (_ARCHIVE_EXT_RE.search(name) or _INSTALLER_EXT_RE.search(name)):
        name = "toolkit.bin"
    dest = dest_dir / name
    print(f"[INFO] toolkit try download: {url}")
    try:
        session = requests.Session()
        session.trust_env = False
        session.verify = False
        proxy_tries = [PROXIES, {}] if PROXIES else [{}]
        last_error: Exception | None = None
        written = 0
        downloaded = False
        for proxies in proxy_tries:
            try:
                with session.get(
                    url,
                    headers={"User-Agent": resolve_ua("Chrome")},
                    timeout=180,
                    stream=True,
                    verify=False,
                    proxies=proxies,
                ) as response:
                    response.raise_for_status()
                    written = 0
                    with dest.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 256):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            written += len(chunk)
                downloaded = True
                break
            except Exception as exc:
                last_error = exc
                dest.unlink(missing_ok=True)
        if not downloaded:
            raise last_error or RuntimeError("download failed")
        print(f"[OK] toolkit downloaded: {dest.name} bytes={written}")
        return dest
    except Exception as exc:
        print(f"[WARN] toolkit download failed: {url} {exc}")
        dest.unlink(missing_ok=True)
        return None


def _unwrap_crx(archive: Path) -> Path:
    data = archive.read_bytes()
    marker = data.find(b"PK\x03\x04")
    if marker <= 0:
        return archive
    dest = archive.with_name(archive.stem + ".zip")
    dest.write_bytes(data[marker:])
    return dest


def _extract_archive(archive: Path, dest_dir: Path) -> bool:
    name = archive.name.lower()
    try:
        if name.endswith(".crx"):
            archive = _unwrap_crx(archive)
            name = archive.name.lower()
        if name.endswith((".zip", ".apk", ".xapk", ".apks", ".xpi", ".crx")):
            import zipfile
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest_dir)
            return True
        if name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz"):
            import tarfile
            with tarfile.open(archive) as tf:
                tf.extractall(dest_dir)
            return True
        if name.endswith(".7z"):
            seven = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz")
            if seven:
                result = subprocess.run(
                    [seven, "x", str(archive), f"-o{dest_dir}", "-y"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "7z failed")
            import py7zr
            with py7zr.SevenZipFile(archive, "r") as zf:
                names = [
                    item for item in zf.getnames()
                    if Path(item).suffix.lower() in _TOOLKIT_TEXT_EXT
                ]
                if names:
                    zf.extract(path=dest_dir, targets=names)
                else:
                    zf.extractall(path=dest_dir)
            return True
        if name.endswith(".rar"):
            import rarfile
            with rarfile.RarFile(archive) as rf:
                rf.extractall(dest_dir)
            return True
        seven = shutil.which("7z") or shutil.which("7za") or shutil.which("7zz")
        if seven:
            result = subprocess.run(
                [seven, "x", str(archive), f"-o{dest_dir}", "-y"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True
        print(f"[WARN] toolkit unsupported archive: {archive.name}")
        return False
    except Exception as exc:
        print(f"[WARN] toolkit extract failed: {archive.name} {exc}")
        return False


def _collect_toolkit_sub_urls(root: Path) -> list[str]:
    url_re = re.compile(r"https?://[^\s\"'<>]+", re.I)
    found: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TOOLKIT_TEXT_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for raw in url_re.findall(text):
            link = raw.rstrip("\\").rstrip(").,;]")
            if not link.startswith("http"):
                continue
            if _TOOLKIT_SKIP_HOST_RE.search(link):
                continue
            if _ARCHIVE_EXT_RE.search(link):
                continue
            parsed = urlparse(link)
            host = parsed.netloc.lower()
            path = parsed.path.lower()
            if host in {"github.com", "www.github.com"} and "/raw/" not in path:
                continue
            if re.search(
                r"\.(?:html?|png|jpe?g|gif|svg|webp|js|css|exe|dmg|apk|msi|iso|md)(?:$|[?#])",
                link,
                re.I,
            ):
                continue
            if re.search(r"\.(?:yaml|yml|json|txt)(?:$|[?#])", link, re.I):
                found.append(link)
                continue
            if "raw.githubusercontent.com" in host or "/raw/" in path:
                found.append(link)
    return unique_ordered(found)


def _collect_toolkit_embedded_proxies(root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _TOOLKIT_CONFIG_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        global _YAML_WARN_SILENT
        _YAML_WARN_SILENT = True
        try:
            nodes = extract_proxies(text)
        finally:
            _YAML_WARN_SILENT = False
        if nodes:
            found.extend(nodes)
    return found


def _toolkit_path_parts(path: str) -> list[str]:
    return [p for p in str(path or "").split("/") if p]


def _toolkit_tail_parts(path: str) -> list[str]:
    parts = _toolkit_path_parts(path)
    return parts[-6:] if len(parts) > 6 else parts


def _toolkit_merge_key(url: str) -> tuple[str, ...]:
    if str(url).startswith("embedded:"):
        return ("embedded",)
    key: list[str] = []
    for part in _toolkit_tail_parts(urlparse(url).path):
        lower = part.lower()
        if part.isdigit() or (len(lower) <= 3 and "." not in lower):
            key.append("#")
        else:
            key.append(lower)
    return tuple(key)


def _toolkit_format_group(urls: list[str]) -> str:
    parsed = [urlparse(item) for item in urls]
    tails = [_toolkit_tail_parts(item.path) for item in parsed]
    width = max((len(tail) for tail in tails), default=0)
    rendered: list[str] = []
    for index in range(width):
        values: list[str] = []
        for tail in tails:
            if index < len(tail):
                values.append(tail[index])
        unique = list(dict.fromkeys(values))
        if len(unique) == 1:
            rendered.append(unique[0])
        elif unique and all(item.isdigit() or (len(item) <= 3 and "." not in item) for item in unique):
            ordered = list(dict.fromkeys(unique))
            rendered.append("{" + "|".join(ordered) + "}")
        elif unique and all(item.isdigit() for item in unique):
            rendered.append("{" + "|".join(sorted(unique, key=int)) + "}")
        else:
            rendered.append("{" + "|".join(unique) + "}")
    prefixes: list[list[str]] = []
    for item, tail in zip(parsed, tails):
        parts = _toolkit_path_parts(item.path)
        head = parts[: max(0, len(parts) - len(tail))]
        prefixes.append([item.netloc, *head])
    shared: list[str] = []
    if len(prefixes) >= 2:
        while prefixes and all(len(item) > 1 and item[-1] == prefixes[0][-1] for item in prefixes):
            shared.insert(0, prefixes[0][-1])
            for item in prefixes:
                item.pop()
    unique_prefix = ["/".join(item) for item in prefixes if item]
    unique_prefix = list(dict.fromkeys(unique_prefix))
    if len(unique_prefix) <= 1:
        origin = "https://" + (unique_prefix[0] if unique_prefix else "")
    else:
        origin = "https://{" + "|".join(unique_prefix) + "}"
    rest = [part for part in (shared + rendered) if part]
    if rest and origin:
        return origin + "/" + "/".join(rest)
    return origin or "/".join(rest)


def _print_toolkit_groups(hits: list[tuple[str, int]]) -> None:
    buckets: dict[tuple[str, ...], list[tuple[str, int]]] = {}
    order: list[tuple[str, ...]] = []
    for url, count in hits:
        key = _toolkit_merge_key(url)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((url, count))
    for key in order:
        rows = buckets[key]
        total = sum(count for _, count in rows)
        if key == ("embedded",):
            print(f"[OK] proxies={total} embedded=archive-config")
            continue
        label = _toolkit_format_group([url for url, _ in rows])
        print(f"[OK] proxies={total} url={label}")


def _collect_toolkit_candidates(page_url: str, prefer: str = "") -> list[str]:
    kind = _toolkit_kind(page_url)
    if kind == "probe":
        kind = _probe_payload(page_url)
    print(f"[INFO] toolkit try {kind}: {page_url}")
    if kind in {"chrome", "edge", "firefox"}:
        return _store_package_urls(kind, page_url)
    if kind == "direct":
        return [page_url]
    if kind == "release":
        return _expand_github_release_assets(page_url, prefer=prefer)
    body = ""
    try:
        body = fetch_text(page_url)
    except Exception:
        body = ""
    links = _collect_archive_links(body, page_url)
    return _rank_package_links(links, prefer=prefer)


def discover_toolkit(page_url: str, prefer: str = "") -> list[str]:
    global _TOOLKIT_EMBEDDED
    _TOOLKIT_EMBEDDED = []
    page_url = page_url.strip()
    archives = unique_ordered(_collect_toolkit_candidates(page_url, prefer=prefer))
    if not archives:
        print(f"[WARN] toolkit discovery failed: {page_url}")
        return []
    work = Path(tempfile.mkdtemp(prefix="toolkit-"))
    try:
        for archive_url in archives:
            archive = _download_archive(archive_url, work)
            if not archive:
                continue
            unpack = work / "unpack"
            os.makedirs(str(unpack), exist_ok=True)
            if not _extract_archive(archive, unpack):
                continue
            embedded = _collect_toolkit_embedded_proxies(unpack)
            urls = _collect_toolkit_sub_urls(unpack)
            if embedded:
                _TOOLKIT_EMBEDDED = embedded
                print(f"[OK] toolkit embedded proxies={len(embedded)} archive={archive.name}")
            if urls:
                print(f"[OK] toolkit discovered subs={len(urls)} archive={archive.name}")
            if embedded or urls:
                return urls
            print(f"[WARN] toolkit empty bundle: {archive.name}")
        print(f"[WARN] toolkit discovery failed: {page_url}")
        return []
    finally:
        shutil.rmtree(work, ignore_errors=True)


def discover_article(feed_url: str, prefer: str = "") -> list[str]:
    body = ""
    try:
        body = fetch_text(feed_url)
    except Exception:
        body = ""

    pages: list[str] = []
    via_feed = False
    parsed = None
    try:
        import feedparser
        parsed = feedparser.parse(body) if body else None
    except ImportError as exc:
        print(f"[WARN] article feedparser missing: {exc}")
        parsed = None
    except Exception:
        parsed = None
    if parsed and parsed.entries:
        def entry_stamp(entry: Any) -> str:
            title = str(getattr(entry, "title", "") or "")
            link = str(getattr(entry, "link", "") or "")
            stamp = _page_stamp(title)
            if stamp != "00000000":
                return stamp
            stamp = _page_stamp(link)
            if stamp != "00000000":
                return stamp
            parsed_time = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if parsed_time:
                return f"{parsed_time.tm_year:04d}{parsed_time.tm_mon:02d}{parsed_time.tm_mday:02d}"
            return "00000000"

        ranked = sorted(parsed.entries[:20], key=entry_stamp, reverse=True)[:10]
        pages = [str(getattr(entry, "link", "") or "") for entry in ranked]
        pages = [page for page in pages if page]
        if pages:
            via_feed = True
            print(f"[INFO] article try feed: {feed_url}")
    if not pages and body:
        pages = _collect_article_links(body, feed_url)
        pages = sorted(pages, key=_page_stamp, reverse=True)[:10]
        if pages:
            print(f"[INFO] article try page: {feed_url}")

    for page in unique_ordered(pages):
        found = discover_sublink(page, prefer=prefer)
        if found:
            return found
    print(f"[WARN] article discovery failed: {feed_url}")
    return []


def unique_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def sanitize_and_deduplicate(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_fingerprints: set[str] = set()
    seen_names: set[str] = set()
    result: list[dict[str, Any]] = []

    for index, raw in enumerate(proxies, start=1):
        proxy = normalize_proxy(raw, index)
        if not proxy:
            continue

        fingerprint = proxy_fingerprint(proxy)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        base_name = str(proxy["name"]).strip() or f"node-{index}"
        name = base_name
        suffix = 2
        while name in seen_names:
            name = f"{base_name}-{suffix}"
            suffix += 1
        proxy["name"] = name
        seen_names.add(name)
        result.append(proxy)
    return result


def normalize_proxy(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    proxy = {key: value for key, value in raw.items() if value is not None}
    proxy_type = str(proxy.get("type", "")).lower().strip()
    if proxy_type not in SUPPORTED_PROXY_TYPES:
        return None

    if proxy_type == "hy2":
        proxy_type = "hysteria2"
    proxy["type"] = proxy_type

    if proxy_type == "wireguard":
        if not proxy.get("server") or not proxy.get("port"):
            return None
        if not proxy.get("private-key") or not proxy.get("public-key"):
            return None
        proxy["udp"] = True

    # 修复常见无效 vless encryption 值（部分免费源会把 Reality 公钥等塞进 encryption 字段）
    if proxy_type == "vless":
        enc = str(proxy.get("encryption", "")).strip()
        if not enc or enc.lower() == "none":
            proxy["encryption"] = "none"
        elif len(enc) > 32 or "mlkem" in enc.lower() or "x25519" in enc.lower() or "." in enc:
            # 非法长字符串或包含密钥特征，强制改为 none
            proxy["encryption"] = "none"

    if proxy_type == "ss":
        plugin_opts = proxy.get("plugin-opts")
        if isinstance(plugin_opts, dict):
            mode = str(plugin_opts.get("mode", "")).strip()
            if not mode:
                proxy.pop("plugin", None)
                proxy.pop("plugin-opts", None)
        obfs = str(proxy.get("obfs", "")).strip()
        if "obfs" in proxy and not obfs:
            proxy.pop("obfs", None)
            proxy.pop("obfs-host", None)

    name = str(proxy.get("name", "")).strip() or f"node-{index}"
    name = name.replace("🇨🇳", "🇹🇼").replace("中国", "")
    server = str(proxy.get("server", "")).strip()
    if not server:
        return None

    try:
        port = int(proxy.get("port"))
    except Exception:
        return None
    if port <= 0 or port > 65535:
        return None

    proxy["name"] = name
    proxy["server"] = server
    proxy["port"] = port

    # 空 flow 会让部分客户端/覆写异常，直接去掉
    if proxy.get("flow") is not None and str(proxy.get("flow")).strip() == "":
        proxy.pop("flow", None)

    # reality short-id 必须是字符串，避免 YAML 把 953e8078 读成科学计数法
    reality = proxy.get("reality-opts")
    if isinstance(reality, dict) and reality.get("short-id") is not None:
        reality = dict(reality)
        reality["short-id"] = str(reality["short-id"]).strip()
        proxy["reality-opts"] = reality

    # 截断被污染的 ws path
    ws_opts = proxy.get("ws-opts")
    if isinstance(ws_opts, dict):
        path = str(ws_opts.get("path") or "")
        path = path.split("|", 1)[0].split("?", 1)[0].strip() or "/"
        ws_opts = dict(ws_opts)
        ws_opts["path"] = path
        proxy["ws-opts"] = ws_opts

    return proxy


def proxy_core_key(proxy: dict[str, Any]) -> str:
    proxy_type = str(proxy.get("type") or "").lower()
    secret = str(
        proxy.get("uuid")
        or proxy.get("password")
        or proxy.get("auth-str")
        or proxy.get("auth_str")
        or proxy.get("private-key")
        or ""
    )
    important = {
        "type": proxy_type,
        "server": str(proxy.get("server") or "").strip().lower(),
        "port": str(proxy.get("port") or ""),
        "secret": secret,
        "cipher": str(proxy.get("cipher") or "") if proxy_type == "ss" else "",
    }
    return json.dumps(important, sort_keys=True, ensure_ascii=True)


def proxy_fingerprint(proxy: dict[str, Any]) -> str:
    return hashlib.sha256(proxy_core_key(proxy).encode("utf-8")).hexdigest()


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def find_or_install_mihomo() -> Path:
    # 优先使用已有的 Clash Verge 内核
    existing = Path(r"C:\Program Files\Clash Verge\verge-mihomo-alpha.exe")
    if existing.exists():
        print(f"[OK] using existing proxy engine: {existing}")
        return existing

    for name in ("mihomo", "clash-meta", "clash"):
        found = shutil.which(name)
        if found:
            print(f"[OK] using proxy engine: {found}")
            return Path(found)

    install_dir = Path(tempfile.gettempdir()) / "free-node-autotest-mihomo"
    os.makedirs(str(install_dir), exist_ok=True)
    binary = install_dir / ("mihomo.exe" if os.name == "nt" else "mihomo")
    if binary.exists():
        print(f"[OK] using cached proxy engine: {binary}")
        return binary

    url, expected_sha256 = select_mihomo_asset()
    print(f"[INFO] downloading proxy engine: {url}")
    archive = download_file(url, install_dir)
    verify_file_sha256(archive, expected_sha256)
    extracted = extract_mihomo_binary(archive, install_dir)
    extracted.chmod(extracted.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if extracted != binary:
        shutil.copy2(extracted, binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binary


def _asset_sha256(asset: dict[str, Any]) -> str:
    digest = str(asset.get("digest") or "").strip()
    if digest.lower().startswith("sha256:"):
        return digest.split(":", 1)[1].strip().lower()
    return ""


def _fetch_checksum_text(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": resolve_ua("ClashMeta")},
        timeout=SOURCE_TIMEOUT,
        verify=False,
        proxies=PROXIES,
    )
    response.raise_for_status()
    return response.text


def _checksum_from_text(text: str, filename: str) -> str:
    needle = filename.lower()
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*").lower().endswith(needle):
            candidate = parts[0].strip().lower()
            if re.fullmatch(r"[0-9a-f]{64}", candidate):
                return candidate
        if len(parts) >= 1 and re.fullmatch(r"[0-9a-f]{64}", parts[0].strip().lower()):
            if needle in line.lower():
                return parts[0].strip().lower()
    text = text.strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", text):
        return text
    return ""


def select_mihomo_asset() -> tuple[str, str]:
    api_url = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
    data = requests.get(
        api_url,
        headers={"User-Agent": resolve_ua("ClashMeta")},
        timeout=SOURCE_TIMEOUT,
        verify=False,
        proxies=PROXIES,
    ).json()
    assets = data.get("assets", [])
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        os_token = "darwin"
    elif system == "android":
        os_token = "android"
    elif system == "linux":
        os_token = "linux"
    elif system == "windows":
        os_token = "windows"
    else:
        raise RuntimeError(f"unsupported OS for Mihomo download: {system}")

    if machine in {"x86_64", "amd64"}:
        arch_tokens = ["amd64"]
    elif machine in {"arm64", "aarch64", "armv8l", "armv8"}:
        arch_tokens = ["arm64-v8", "arm64"]
    elif machine in {"armv7l", "armv7", "arm"}:
        arch_tokens = ["armv7", "armv6"]
    else:
        raise RuntimeError(f"unsupported architecture for Mihomo download: {machine}")

    checksum_assets: dict[str, str] = {}
    sum_files: list[str] = []
    binaries: list[tuple[str, str, str]] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        lower = name.lower()
        download_url = str(asset.get("browser_download_url", ""))
        if not download_url:
            continue
        if lower.endswith(".sha256") or lower.endswith(".sha256sum"):
            checksum_assets[lower.rsplit(".", 1)[0]] = download_url
            continue
        if lower in {"checksums.txt", "sha256sums.txt", "sha256sums", "checksums"}:
            sum_files.append(download_url)
            continue
        if os_token not in lower:
            continue
        if not any(token in lower for token in arch_tokens):
            continue
        if "compatible" in lower:
            continue
        if not (lower.endswith(".gz") or lower.endswith(".zip")):
            continue
        binaries.append((name, download_url, _asset_sha256(asset)))

    if not binaries:
        raise RuntimeError("no matching Mihomo release asset found")
    name, url, expected = binaries[0]
    if expected:
        print(f"[INFO] release digest sha256={expected} asset={name}")
        return url, expected

    stem = name.lower()
    for key, checksum_url in checksum_assets.items():
        if stem.startswith(key) or key.startswith(stem):
            expected = _checksum_from_text(_fetch_checksum_text(checksum_url), name)
            if expected:
                print(f"[INFO] checksum file sha256={expected} asset={name}")
                return url, expected
    for checksum_url in sum_files:
        expected = _checksum_from_text(_fetch_checksum_text(checksum_url), name)
        if expected:
            print(f"[INFO] checksums list sha256={expected} asset={name}")
            return url, expected
    raise RuntimeError(f"no sha256 found for Mihomo asset: {name}")


def verify_file_sha256(path: Path, expected: str) -> None:
    expected = expected.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError(f"invalid sha256 value: {expected}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().lower()
    if actual != expected:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"proxy engine checksum mismatch expected={expected} actual={actual}")
    print(f"[OK] proxy engine sha256 verified: {actual}")


def download_file(url: str, directory: Path) -> Path:
    target = directory / Path(url.split("?")[0]).name
    # 增加 verify=False
    with requests.get(url, stream=True, timeout=SOURCE_TIMEOUT, verify=False, proxies=PROXIES) as response:
        response.raise_for_status()
        with target.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 512):
                if chunk:
                    file.write(chunk)
    return target


def extract_mihomo_binary(archive: Path, directory: Path) -> Path:
    if archive.suffix == ".gz" and not archive.name.endswith(".tar.gz"):
        target = directory / archive.name[:-3]
        with gzip.open(archive, "rb") as source, target.open("wb") as dest:
            shutil.copyfileobj(source, dest)
        return target

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(directory)
        for path in directory.rglob("*"):
            if path.is_file() and "mihomo" in path.name.lower():
                return path

    raise RuntimeError(f"unsupported Mihomo archive: {archive}")


class QuotedDumper(yaml.SafeDumper):
    pass


_QUOTE_BOOLS = {
    "true", "false", "yes", "no", "on", "off", "y", "n", "null", "~",
}
_RISKY_SCALAR = re.compile(
    r"^(?:"
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)"  # 科学计数 953e8078
    r"|[-+]?\d+:\d+(?::\d+(?:\.\d*)?)?"              # YAML 1.1 六十进制
    r"|[-+]?0[0-9]+"                                 # 前导 0
    r")$"
)


def _needs_quote(text: str) -> bool:
    if text == "" or text.strip() != text:
        return True
    if text[0] in "-?:{}[]&*!#|>%@`'\",":
        return True
    if any(ch in text for ch in ":#[]{},"):
        return True
    if text.lower() in _QUOTE_BOOLS:
        return True
    if _RISKY_SCALAR.match(text):
        return True
    return False


def _represent_str(dumper: yaml.Dumper, data: str):
    style = "'" if _needs_quote(data) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


QuotedDumper.add_representer(str, _represent_str)


_SEP_JUST_PRINTED = False


def dump_yaml(data: Any) -> str:
    return yaml.dump(
        data,
        Dumper=QuotedDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def write_raw_backup(proxies: list[dict[str, Any]]) -> None:
    os.makedirs(str(RAW_PATH.parent), exist_ok=True)
    nodes = [dict(item) for item in proxies if isinstance(item, dict)]
    names = [str(item.get("name") or "") for item in nodes]
    payload = {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "ipv6": True,
        "unified-delay": True,
        "tcp-concurrent": True,
        "global-client-fingerprint": "chrome",
        "generated-by": f"free-node-autotest-{VERSION}-raw",
        "generated-at": datetime.now(timezone.utc).isoformat(),
        "proxies": nodes,
        "proxy-groups": [
            {
                "name": "URL-TEST",
                "type": "url-test",
                "proxies": names or ["DIRECT"],
                "url": TEST_URL,
                "interval": 120,
            }
        ],
        "rules": [
            "MATCH,URL-TEST",
        ],
    }
    RAW_PATH.write_text(dump_yaml(payload), encoding="utf-8")
    global _SEP_JUST_PRINTED
    _SEP_JUST_PRINTED = False
    print_sep()
    print(f"[INFO] raw backup written path={RAW_PATH} proxies={len(nodes)}")


def history_file_stamp(name: str) -> str:
    match = re.search(r"(\d{4})-(20\d{6})", name)
    if match:
       return match.group(2) + match.group(1)
    match = re.search(r"(20\d{6})-(\d{4})", name)
    if match:
        return match.group(1) + match.group(2)
    return ""


def load_previous_source_proxies(source: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = str(source.get("prefix") or "")
    name = str(source.get("name") or "")
    if not HISTORY_DIR.is_dir():
        print(f"[WARN] source={name} no proxies; raw backup dir missing, skip reuse")
        return []
    ranked: list[tuple[str, Path]] = []
    for path in HISTORY_DIR.glob("*raw*.yaml"):
        stamp = history_file_stamp(path.name)
        if stamp:
            ranked.append((stamp, path))
    ranked.sort(reverse=True)
    if not ranked:
        print(f"[WARN] source={name} no proxies; no raw backup file, skip reuse")
        return []
    for stamp, path in ranked:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] raw backup unreadable file={path.name} error={exc}")
            continue
        items = data.get("proxies") if isinstance(data, dict) else None
        if not isinstance(items, list):
            continue
        found = []
        for item in items:
            if not isinstance(item, dict):
                continue
            node_name = str(item.get("name") or "")
            if prefix and node_name.startswith(prefix):
                found.append(dict(item))
        if found:
            print(
                f"[INFO] proxies={len(found)} source={name} reused previous raw "
                f"file={path.name} stamp={stamp}"
            )
            return found
    print(f"[WARN] source={name} no proxies; raw backups have no prefix={prefix!r}, skip reuse")
    return []


def write_benchmark_config(path: Path, proxies: list[dict[str, Any]], controller_port: int) -> None:
    names = [str(proxy["name"]) for proxy in proxies]
    config = {
        "mixed-port": find_free_port(),
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "external-controller": f"127.0.0.1:{controller_port}",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "BENCHMARK",
                "type": "select",
                "proxies": names or ["DIRECT"],
            }
        ],
        "rules": ["MATCH,BENCHMARK"],
    }
    path.write_text(dump_yaml(config), encoding="utf-8")


def wait_for_controller(controller_url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("Mihomo exited before controller became ready")
        try:
            response = requests.get(f"{controller_url}/version", timeout=1, verify=False)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("Mihomo controller did not become ready")


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _start_mihomo_for_batch(
    engine: Path,
    temp_dir: Path,
    config_path: Path,
    controller_url: str,
    controller_port: int,
    proxies: list[dict[str, Any]],
) -> tuple[subprocess.Popen[str] | None, str]:
    write_benchmark_config(config_path, proxies, controller_port)
    process = subprocess.Popen(
        [str(engine), "-d", str(temp_dir), "-f", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_controller(controller_url, process)
        return process, ""
    except Exception as exc:
        try:
            stdout, stderr = process.communicate(timeout=2)
        except Exception:
            stdout, stderr = "", ""
        _stop_process(process)
        message = f"{exc}\n{stderr}\n{stdout}"
        print(f"[WARN] batch start failed size={len(proxies)}")
        if stderr:
            print(f"[WARN] Mihomo stderr: {stderr[:500]}")
        return None, message


def _benchmark_batch(
    engine: Path,
    temp_dir: Path,
    config_path: Path,
    controller_url: str,
    controller_port: int,
    proxies: list[dict[str, Any]],
) -> list[ProxyMetric]:
    if not proxies:
        return []

    process, error = _start_mihomo_for_batch(
        engine, temp_dir, config_path, controller_url, controller_port, proxies
    )
    if process is not None:
        try:
            return run_delay_tests(controller_url, proxies)
        finally:
            _stop_process(process)

    if len(proxies) == 1:
        bad = proxies[0]
        print(
            f"[DROP] isolate bad proxy name={bad.get('name')} "
            f"server={bad.get('server')}:{bad.get('port')}"
        )
        if error:
            print(f"[DROP] reason: {error[:300]}")
        return []

    mid = max(1, len(proxies) // 2)
    left = proxies[:mid]
    right = proxies[mid:]
    print(f"[WARN] split batch {len(proxies)} -> {len(left)} + {len(right)}")
    return _benchmark_batch(
        engine, temp_dir, config_path, controller_url, controller_port, left
    ) + _benchmark_batch(
        engine, temp_dir, config_path, controller_url, controller_port, right
    )


def benchmark_proxies(proxies: list[dict[str, Any]]) -> list[ProxyMetric]:
    global _SEP_JUST_PRINTED
    if not proxies:
        return []

    engine = find_or_install_mihomo()
    _SEP_JUST_PRINTED = False
    print_sep()
    with tempfile.TemporaryDirectory(prefix="free-node-autotest-") as temp_name:
        temp_dir = Path(temp_name)
        config_path = temp_dir / "benchmark.yaml"
        controller_port = find_free_port()
        controller_url = f"http://127.0.0.1:{controller_port}"
        metrics = _benchmark_batch(
            engine, temp_dir, config_path, controller_url, controller_port, list(proxies)
        )
        _SEP_JUST_PRINTED = False
        print_sep()
        if not metrics:
            raise RuntimeError("Mihomo benchmark produced no live proxies")
        return metrics


def run_delay_tests(controller_url: str, proxies: list[dict[str, Any]]) -> list[ProxyMetric]:
    workers = max(1, min(MAX_WORKERS, len(proxies)))
    metrics: list[ProxyMetric] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(test_single_proxy, controller_url, proxy): proxy
            for proxy in proxies
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            proxy = futures[future]
            try:
                metric = future.result()
            except Exception as exc:
                print(f"[DROP] {proxy.get('name')} failed: {exc}")
                continue
            if metric:
                metrics.append(metric)
            if completed % 25 == 0 or completed == len(futures):
                print(f"[INFO] tested {completed}/{len(futures)} kept={len(metrics)}")
    return metrics


def test_single_proxy(controller_url: str, proxy: dict[str, Any]) -> ProxyMetric | None:
    name = str(proxy["name"])
    url = (
        f"{controller_url}/proxies/{quote(name, safe='')}/delay"
        f"?timeout={LATENCY_TIMEOUT_MS}&url={quote(TEST_URL, safe='')}"
    )
    response = requests.get(url, timeout=(LATENCY_TIMEOUT_MS / 1000) + 3, verify=False)
    if response.status_code != 200:
        return None
    data = response.json()
    latency = int(data.get("delay", 0))
    if latency <= 0 or latency > LATENCY_TIMEOUT_MS:
        return None
    region = detect_region(name)
    score = health_score(name, latency, region)
    return ProxyMetric(proxy=proxy, latency=latency, region=region, health_score=score)


def detect_region(name: str) -> str:
    text = name.lower()
    patterns = {
        "HK": (
            "regex:\\bhk\\b",
            "hong kong",
            "\\u9999\\u6e2f",
            "\U0001f1ed\U0001f1f0",
        ),
        "JP": (
            "regex:\\bjp\\b",
            "japan",
            "\\u65e5\\u672c",
            "\U0001f1ef\U0001f1f5",
        ),
        "US": (
            "regex:\\bus\\b",
            "regex:\\busa\\b",
            "united states",
            "america",
            "\\u7f8e\\u56fd",
            "\\u7f8e\\u570b",
            "\U0001f1fa\U0001f1f8",
        ),
        "SG": (
            "regex:\\bsg\\b",
            "singapore",
            "\\u65b0\\u52a0\\u5761",
            "\U0001f1f8\U0001f1ec",
        ),
    }
    for region, tokens in patterns.items():
        for token in tokens:
            if token.startswith("regex:"):
                if re.search(token.removeprefix("regex:"), text):
                    return region
                continue
            if token.startswith("\\u"):
                token = token.encode("utf-8").decode("unicode_escape")
            if token in text:
                return region
    return "OTHER"


def region_bonus(region: str) -> int:
    if region in {"HK", "SG", "JP"}:
        return 3
    if region == "US":
        return 2
    return 1


def health_score(name: str, latency: int, region: str) -> float:
    stability_seed = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:12], 16)
    stability = random.Random(stability_seed).random()
    latency_term = LATENCY_TIMEOUT_MS / max(int(latency), 1)
    return latency_term + region_bonus(region) + stability * 0.1


def low_latency_pool(metrics: list[ProxyMetric]) -> list[str]:
    if not metrics:
        return ["DIRECT"]
    ordered = sorted(metrics, key=lambda item: (item.latency, -item.health_score))
    size = min(max(3, len(ordered) // 5), 30, len(ordered))
    return [item.proxy["name"] for item in ordered[:size]]


def names_for_region(metrics: list[ProxyMetric], region: str) -> list[str]:
    names = [item.proxy["name"] for item in metrics if item.region == region]
    if names:
        return names
    if metrics:
        return [item.proxy["name"] for item in metrics[: min(5, len(metrics))]]
    return ["DIRECT"]


def build_direct_fallback_metric() -> ProxyMetric:
    proxy = {"name": "DIRECT-FALLBACK", "type": "direct", "udp": True}
    return ProxyMetric(proxy=proxy, latency=LATENCY_TIMEOUT_MS, region="OTHER", health_score=0.0)


def load_existing_metrics() -> list[ProxyMetric]:
    if not HISTORY_DIR.is_dir():
        print("[WARN] clash fallback dir missing, skip reuse")
        return []
    ranked: list[tuple[str, Path]] = []
    for path in HISTORY_DIR.glob("*clash*.yaml"):
        stamp = history_file_stamp(path.name)
        if stamp:
            ranked.append((stamp, path))
    ranked.sort(reverse=True)
    if not ranked:
        print("[WARN] no clash backup file in history, skip reuse")
        return []
    for stamp, path in ranked:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[WARN] clash backup unreadable file={path.name} error={exc}")
            continue
        items = data.get("proxies") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            continue
        metrics: list[ProxyMetric] = []
        for proxy in items:
            if not isinstance(proxy, dict):
                continue
            name = str(proxy.get("name", ""))
            region = detect_region(name)
            metrics.append(
                ProxyMetric(
                    proxy=dict(proxy),
                    latency=LATENCY_TIMEOUT_MS,
                    region=region,
                    health_score=health_score(name, LATENCY_TIMEOUT_MS, region),
                )
            )
        if metrics:
            print(
                f"[INFO] reused previous clash proxies={len(metrics)} "
                f"file={path.name} stamp={stamp}"
            )
            return metrics
    print("[WARN] clash backups have no proxies, skip reuse")
    return []


def build_config(metrics: list[ProxyMetric]) -> dict[str, Any]:
    if not metrics:
        metrics = [build_direct_fallback_metric()]

    proxies = [item.proxy for item in metrics]
    all_names = [item.proxy["name"] for item in metrics]
    hk_names = names_for_region(metrics, "HK")
    jp_names = names_for_region(metrics, "JP")
    us_names = names_for_region(metrics, "US")
    fast_names = low_latency_pool(metrics)

    return {
        "mixed-port": 7890,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "ipv6": True,
        "unified-delay": True,
        "tcp-concurrent": True,
        "global-client-fingerprint": "chrome",
        "generated-by": f"free-node-autotest-{VERSION}",
        "generated-at": datetime.now(timezone.utc).isoformat(),
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "URL-TEST",
                "type": "url-test",
                "proxies": all_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "HK-POOL",
                "type": "url-test",
                "proxies": hk_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "JP-POOL",
                "type": "url-test",
                "proxies": jp_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "US-POOL",
                "type": "url-test",
                "proxies": us_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "FAST-POOL",
                "type": "url-test",
                "proxies": fast_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "FALLBACK",
                "type": "fallback",
                "proxies": ["URL-TEST", "HK-POOL", "JP-POOL", "US-POOL"],
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "PROXY",
                "type": "select",
                "proxies": ["URL-TEST", "FALLBACK"],
            },
        ],
        "rules": [
            "GEOIP,CN,DIRECT",
            "MATCH,PROXY",
        ],
    }


def write_config(config: dict[str, Any]) -> None:
    os.makedirs(str(OUTPUT_PATH.parent), exist_ok=True)
    OUTPUT_PATH.write_text(dump_yaml(config), encoding="utf-8")


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get("proxies"), list) or not config["proxies"]:
        raise RuntimeError("generated config has no proxies")
    groups = config.get("proxy-groups", [])
    group_names = {group.get("name") for group in groups if isinstance(group, dict)}
    missing = [name for name in REQUIRED_GROUPS if name not in group_names]
    if missing:
        raise RuntimeError(f"generated config missing groups: {missing}")
    rules = config.get("rules", [])
    for rule in (
        "GEOIP,CN,DIRECT",
        "MATCH,PROXY",
    ):
        if rule not in rules:
            raise RuntimeError(f"generated config missing rule: {rule}")


def source_prefix_of(name: str) -> str:
    text = str(name or "")
    if text.startswith("[") and "]" in text:
        return text.split("]", 1)[0] + "]"
    return "(无前缀)"


def count_live_by_prefix(metrics: list[ProxyMetric]) -> dict[str, int]:
    tallies: dict[str, int] = {}
    for item in metrics:
        key = source_prefix_of(str(item.proxy.get("name") or ""))
        tallies[key] = tallies.get(key, 0) + 1
    return tallies


def _live_cell(text: str, width: int, align: str = "<") -> str:
    raw = str(text)
    visual = 0
    for ch in raw:
        visual += 2 if ord(ch) > 127 else 1
    pad = max(0, width - visual)
    if align == ">":
        return " " * pad + raw
    return raw + " " * pad


def print_source_live_stats(
    collected: dict[str, int],
    unique: dict[str, int],
    raw_live: dict[str, int],
    capped: dict[str, int],
) -> None:
    global _SEP_JUST_PRINTED
    prefixes: list[str] = []
    seen: set[str] = set()
    for source in SOURCE_GROUPS:
        key = str(source.get("prefix") or "").strip() or f"[{source.get('name')}]"
        if key not in seen:
            prefixes.append(key)
            seen.add(key)
    for key in list(collected) + list(unique) + list(raw_live) + list(capped):
        if key not in seen:
            prefixes.append(key)
            seen.add(key)
    rows = []
    for key in prefixes:
        a = collected.get(key, 0)
        b = unique.get(key, 0)
        c = raw_live.get(key, 0)
        d = capped.get(key, 0)
        rows.append((key, a, b, c, d))
    if not rows:
        return
    _SEP_JUST_PRINTED = False
    print_sep()
    rule = "+------------------------------+--------+--------+------+--------+"
    print(rule)
    print(
        "| "
        + _live_cell("source", 28)
        + " | "
        + _live_cell("raw", 6, ">")
        + " | "
        + _live_cell("unique", 6, ">")
        + " | "
        + _live_cell("live", 4, ">")
        + " | "
        + _live_cell("capped", 6, ">")
        + " |"
    )
    print(rule)
    for key, a, b, c, d in rows:
        print(
            "| "
            + _live_cell(key, 28)
            + " | "
            + _live_cell(a, 6, ">")
            + " | "
            + _live_cell(b, 6, ">")
            + " | "
            + _live_cell(c, 4, ">")
            + " | "
            + _live_cell(d, 6, ">")
            + " |"
        )
        print(rule)
    _SEP_JUST_PRINTED = False
    print_sep()


def dedupe_metrics_by_core(metrics: list[ProxyMetric]) -> list[ProxyMetric]:
    best: dict[str, ProxyMetric] = {}
    order: list[str] = []
    for item in metrics:
        key = proxy_core_key(item.proxy)
        if key not in best:
            best[key] = item
            order.append(key)
        elif item.health_score > best[key].health_score:
            best[key] = item
    dropped = len(metrics) - len(best)
    if dropped:
        print(f"[INFO] core-dedupe dropped {dropped} same-host variants, kept higher health_score")
    return [best[key] for key in order]


def limit_metrics_per_source(metrics: list[ProxyMetric]) -> list[ProxyMetric]:
    grouped: dict[str, list[ProxyMetric]] = {}
    order: list[str] = []
    for item in metrics:
        key = source_prefix_of(str(item.proxy.get("name") or ""))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(item)

    limited: list[ProxyMetric] = []
    for key in order:
        group = grouped[key]
        if len(group) > MAX_LIVE_PER_SOURCE:
            print(
                f"[INFO] cap live source={key} from {len(group)} to {MAX_LIVE_PER_SOURCE} by health_score"
            )
            global _SEP_JUST_PRINTED
            _SEP_JUST_PRINTED = False
            group = sorted(group, key=lambda item: item.health_score, reverse=True)[:MAX_LIVE_PER_SOURCE]
        limited.extend(group)
    return limited


_SEP_JUST_PRINTED = False


def print_sep() -> None:
    global _SEP_JUST_PRINTED
    if _SEP_JUST_PRINTED:
        return
    print("============================================================")
    _SEP_JUST_PRINTED = True


def print_summary(total_nodes: int, candidates: int, metrics: list[ProxyMetric]) -> None:
    print_sep()
    hk_count = sum(1 for item in metrics if item.region == "HK")
    jp_count = sum(1 for item in metrics if item.region == "JP")
    us_count = sum(1 for item in metrics if item.region == "US")
    avg_latency = round(sum(item.latency for item in metrics) / len(metrics), 2) if metrics else 0
    print(f"[SUMMARY] total_nodes={total_nodes}")
    print(f"[SUMMARY] legal_candidates={candidates}")
    print(f"[SUMMARY] passed_latency_test={len(metrics)}")
    print(f"[SUMMARY] region_HK={hk_count} region_JP={jp_count} region_US={us_count}")
    print(f"[SUMMARY] avg_latency_ms={avg_latency}")
    print(f"[SUMMARY] output={OUTPUT_PATH}")


def main() -> None:
    _bind_dirs()
    total_nodes, candidates, collected_counts = collect_proxies()
    metrics: list[ProxyMetric] = []

    if candidates:
        try:
            metrics = benchmark_proxies(candidates)
        except Exception as exc:
            print(f"[WARN] real latency benchmark unavailable: {exc}")

    if not metrics:
        metrics = load_existing_metrics()
        if metrics:
            print("[WARN] no live nodes passed; reusing previous history clash as degraded fallback")

    if not metrics:
        metrics = [build_direct_fallback_metric()]
        print("[WARN] no live or previous nodes; using DIRECT-FALLBACK degraded config")

    unique_counts: dict[str, int] = {}
    for proxy in candidates:
        key = source_prefix_of(str(proxy.get("name") or ""))
        unique_counts[key] = unique_counts.get(key, 0) + 1
    raw_live = count_live_by_prefix(metrics)
    metrics = dedupe_metrics_by_core(metrics)
    metrics = limit_metrics_per_source(metrics)
    capped_live = count_live_by_prefix(metrics)
    print_source_live_stats(collected_counts, unique_counts, raw_live, capped_live)
    order = {str(proxy["name"]): index for index, proxy in enumerate(candidates)}
    metrics.sort(key=lambda item: order.get(str(item.proxy["name"]), 10**9))
    config = build_config(metrics)
    validate_config(config)
    write_config(config)
    print_summary(total_nodes, len(candidates), metrics)


if __name__ == "__main__":
    print_sep()
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise
    finally:
        _SEP_JUST_PRINTED = False
        print_sep()