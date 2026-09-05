from __future__ import annotations

import base64
import gzip
import hashlib
import html
import importlib.util
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
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse, urlunparse

_REQUIRED_PACKAGES = {
    "requests": "requests",
    "urllib3": "urllib3",
    "yaml": "PyYAML",
}
_OPTIONAL_PACKAGES = {
    "feedparser": "feedparser",
    "py7zr": "py7zr",
    "rarfile": "rarfile",
    "Crypto": "pycryptodome",
}

def _pkg_missing(mod: str) -> bool:
    return importlib.util.find_spec(mod) is None

def _which_any(*names: str) -> str:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    extra = (
        "/usr/bin",
        "/usr/local/bin",
        "/opt/homebrew/bin",
        "/data/data/com.termux/files/usr/bin",
        "/system/bin",
        "/system/xbin",
    )
    for folder in extra:
        for name in names:
            path = Path(folder) / name
            if path.exists() and os.access(path, os.X_OK):
                return str(path)
    return ""


def _have_7z_tool() -> str:
    return _which_any("7z", "7za", "7zz", "7zr", "p7zip")


def _have_rar_tool() -> str:
    return _have_7z_tool() or _which_any("unrar", "unar", "rar", "bsdtar")


_missing_required = [pip for mod, pip in _REQUIRED_PACKAGES.items() if _pkg_missing(mod)]
_missing_optional = [pip for mod, pip in _OPTIONAL_PACKAGES.items() if _pkg_missing(mod)]
if _have_7z_tool():
    _missing_optional = [name for name in _missing_optional if name != "py7zr"]
if _have_rar_tool():
    _missing_optional = [name for name in _missing_optional if name != "rarfile"]
if _missing_required or _missing_optional:
    if _missing_required:
        print("[WARN] required packages missing: " + ", ".join(_missing_required))
    if _missing_optional:
        print("[WARN] optional packages missing: " + ", ".join(_missing_optional))
    print(
        "[WARN] install with: pip install "
        + " ".join(_missing_required + _missing_optional)
    )
if _missing_required:
    raise SystemExit(1)

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
SOURCE_TIMEOUT = 20
CFG_FETCH_TIMEOUT = 12
CFG_FETCH_WORKERS = 24
CFG_FETCH_RETRIES = 1
_DROP_NAMES: list[str] = []
# Temporary diagnostic prints must use prefix [DEBUG], not [INFO]/[OK]/[WARN].
LATENCY_TIMEOUT_MS = 5000
MAX_RETRIES = 2
MAX_WORKERS = int(os.getenv("FREE_NODE_AUTOTEST_MAX_WORKERS", "100"))
MAX_CANDIDATES = int(os.getenv("FREE_NODE_AUTOTEST_MAX_CANDIDATES", "0"))
MAX_LIVE_PER_SOURCE = int(os.getenv("FREE_NODE_AUTOTEST_MAX_LIVE_PER_SOURCE", "50"))
MAX_LIVE_TOTAL = int(os.getenv("FREE_NODE_AUTOTEST_MAX_LIVE_TOTAL", "350"))

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
        "name": "NekoWarp",
        "primary": "https://neko-warp.nloli.xyz/neko_warp.yaml",
        "fallbacks": [],
        "prefix": "[NekoWarp] ",
    },
    {
        "name": "V2Rayshare-RSS",
        "primary": "discover:article:https://v2rayshare.com/feed",
        "fallbacks": [],
        "prefix": "[V2Rayshare-RSS] ",
    },
    {
        "name": "V2Rayshare-SUB",
        "primary": "discover:sublink:https://github.com/firefoxmmx2/v2rayshare_subcription/raw/refs/heads/main/README.md",
        "fallbacks": [
            "https://cdn.jsdelivr.net/gh/firefoxmmx2/v2rayshare_subcription/subscription/mihomo_sub.yaml",
        ],
        "prefix": "[V2Rayshare-SUB] ",
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
        "prefix": "[Free-clash-v2ray] ",
    },
    {
        "name": "Pawdroid",
        "primary": "https://raw.githubusercontent.com/Pawdroid/Free-servers/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
            "https://mirror.v2gh.com/https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        ],
        "prefix": "[Pawdroid] ",
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
        "prefix": "[免费节点8] ",
    },
    {
        "name": "免费节点9-1",
        "primary": "discover:sublink:https://raw.githubusercontent.com/w1770946466/Auto_proxy/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription_num",
        ],
        "prefix": "[免费节点9-1] ",
    },
    {
        "name": "免费节点10",
        "primary": "discover:sublink:https://raw.githubusercontent.com/PuddinCat/BestClash/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/PuddinCat/BestClash/refs/heads/main/proxies.yaml",
        ],
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
        "prefix": "[免费节点11-1] ",
    },
    {
        "name": "Pawdroid-sr-apk",
        "primary": "discover:toolkit:sr-apk:https://github.com/Pawdroid/shadowrocket_for_android/releases",
        "fallbacks": [],
        "prefer": "apk",
        "prefix": "[Pawdroid-sr-apk] ",
    },
    {
        "name": "Pawdroid-ss-apk",
        "primary": "discover:toolkit:ss-apk:https://shadowshare.v2cross.com/",
        "fallbacks": [
            "discover:toolkit:ss-apk:https://github.com/Pawdroid/ShadowShare/releases",
        ],
        "prefer": "apk",
        "prefix": "[Pawdroid-ss-apk] ",
    },
    {
        "name": "Clashfree",
        "primary": "discover:sublink:https://raw.githubusercontent.com/free-nodes/clashfree/refs/heads/main/README.md",
        "fallbacks": [
            {
                "url": "discover:sublink:https://raw.githubusercontent.com/free-nodes/v2rayfree/refs/heads/main/README.md",
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
    "v2rayNG": "v2rayNG/10.10.5",
    "Chrome": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def resolve_ua(name: str = "") -> str:
    key = (name or "ClashMeta").strip()
    return UA_PRESETS.get(key, key)


def _path_search_bases() -> list[Path]:
    bases: list[Path] = []
    try:
        bases.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        bases.append(Path(os.getcwd()))
    except OSError:
        pass
    try:
        bases.append(Path.home())
    except Exception:
        pass
    return bases


def _writable_dir(name: str) -> Path:
    bases = _path_search_bases()
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


def _safe_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or "." not in parsed.netloc:
        return url
    path = quote(parsed.path or "", safe="/-._~@")
    query = quote(parsed.query or "", safe="=&%+-._~")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, parsed.fragment))


def fetch_text(
    url: str,
    retries: int = MAX_RETRIES,
    user_agent: str = "",
    referer: str = "",
    accept: str = "",
    timeout: int | None = None,
) -> str:
    headers = {
        "User-Agent": resolve_ua(user_agent),
        "Accept": accept or "text/plain, text/yaml, application/yaml, */*",
    }
    if referer:
        headers["Referer"] = referer
    url = _safe_http_url(url)
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    proxy_tries = [PROXIES, {}] if PROXIES else [{}]
    last_error: Exception | None = None
    wait = SOURCE_TIMEOUT if timeout is None else timeout
    for proxies in proxy_tries:
        for attempt in range(1, retries + 1):
            try:
                response = session.get(
                    url,
                    headers=headers,
                    timeout=wait,
                    proxies=proxies,
                )
                response.raise_for_status()
                return response.content.decode("utf-8", errors="replace")
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(min(1, attempt))
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
_YAML_WARN_SILENT = True


def _yaml_warn(brief: str) -> None:
    return


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
        source_seen: set[str] = set()
        used_url = ""
        used_toolkit = False
        discover_pages: list[str] = []
        toolkit_hits: list[tuple[str, list[str], int]] = []
        for item in _source_queue(source):
            if source_found:
                break
            url, prefer, exclude = _item_spec(item, source)
            merge_all = False
            if url.startswith("discover:article:"):
                candidates = discover_article(url[len("discover:article:"):], prefer=prefer)
                merge_all = True
                discover_pages = list(_DISCOVER_PAGES)
            elif url.startswith("discover:sublink:"):
                page = url[len("discover:sublink:"):]
                candidates = discover_sublink(
                    page,
                    prefer=prefer,
                    exclude=exclude,
                )
                merge_all = True
                discover_pages = list(_DISCOVER_PAGES) or [_blob_to_raw(page)]
            elif url.startswith("discover:toolkit:"):
                toolkit_spec = url[len("discover:toolkit:"):]
                if toolkit_spec.lower().startswith("ss-apk:"):
                    apk_found, apk_url = _discover_toolkit_ss_apk(
                        source, toolkit_spec[len("ss-apk:"):]
                    )
                    if apk_found:
                        prefix = source.get("prefix", "")
                        for proxy in apk_found:
                            item_proxy = dict(proxy)
                            if prefix:
                                item_proxy["name"] = prefix + str(item_proxy.get("name", "")).strip()
                            source_found.append(item_proxy)
                        used_url = apk_url or url
                    continue
                if toolkit_spec.lower().startswith("sr-apk:"):
                    apk_found, apk_url = _discover_toolkit_sr_apk(
                        source, toolkit_spec[len("sr-apk:"):]
                    )
                    if apk_found:
                        prefix = source.get("prefix", "")
                        for proxy in apk_found:
                            item_proxy = dict(proxy)
                            if prefix:
                                item_proxy["name"] = prefix + str(item_proxy.get("name", "")).strip()
                            source_found.append(item_proxy)
                        used_url = apk_url or url
                    continue
                candidates = discover_toolkit(toolkit_spec, prefer=prefer)
                merge_all = True
                used_toolkit = True
            else:
                candidates = [url]
                print(f"[INFO] source try url: {url}")
            if used_toolkit and _TOOLKIT_EMBEDDED:
                prefix = source.get("prefix", "")
                local_nodes = []
                for proxy in _TOOLKIT_EMBEDDED:
                    item = dict(proxy)
                    if prefix:
                        item["name"] = prefix + str(item.get("name", "")).strip()
                    local_nodes.append(item)
                source_found.extend(local_nodes)
                marks = [proxy_fingerprint(item) for item in local_nodes]
                toolkit_hits.append(("embedded://archive-config", marks, len(local_nodes)))
            pending = unique_ordered(candidates)
            ua = str(source.get("user_agent") or "")
            ref = str(source.get("referer") or "")

            def _ingest(url: str, text: str) -> bool:
                nonlocal used_url
                head = str(text).lstrip()[:64].lower()
                if merge_all and head.startswith(("<!", "<html", "<head", "<title")):
                    return False
                found = extract_proxies(text)
                if not found:
                    if not merge_all:
                        print(f"[WARN] source={source['name']} empty url={url}")
                    return False
                prefix = source.get("prefix", "")
                kept: list[dict[str, Any]] = []
                marks: list[str] = []
                for p in found:
                    if not isinstance(p, dict):
                        continue
                    if prefix:
                        p["name"] = prefix + str(p.get("name", "")).strip()
                    mark = proxy_fingerprint(p)
                    marks.append(mark)
                    if mark in source_seen:
                        continue
                    source_seen.add(mark)
                    kept.append(p)
                toolkit_hits.append((url, marks, len(kept)))
                if not kept:
                    return bool(found)
                source_found.extend(kept)
                used_url = url
                return True

            if merge_all and pending:
                def _fetch_one(url: str) -> tuple[str, str | None, str]:
                    try:
                        body = fetch_text(
                            url,
                            retries=CFG_FETCH_RETRIES,
                            user_agent=ua,
                            referer=ref,
                            timeout=SOURCE_TIMEOUT,
                        )
                        return url, body, ""
                    except Exception as exc:
                        return url, None, str(exc)

                workers = max(1, min(CFG_FETCH_WORKERS, len(pending)))
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(_fetch_one, url) for url in pending]
                    for future in as_completed(futures):
                        url, text, err = future.result()
                        if err or text is None:
                            continue
                        _ingest(url, text)
            else:
                for url in pending:
                    try:
                        text = fetch_text(url, user_agent=ua, referer=ref)
                    except Exception as exc:
                        print(f"[WARN] source={source['name']} skipped url={url} error={exc}")
                        continue
                    if _ingest(url, text):
                        break
                    if source_found:
                        break
        if not source_found:
            print(f"[WARN] source={source['name']} no proxies")
            source_found = load_previous_source_proxies(source)
        else:
            if toolkit_hits:
                _print_toolkit_groups(toolkit_hits)
            if used_toolkit and _TOOLKIT_ARCHIVE_URL:
                extra = f" url={_TOOLKIT_ARCHIVE_URL}"
            elif discover_pages:
                extra = f" url={_aggregate_urls(discover_pages)}"
            elif used_url:
                extra = f" url={used_url.split('?', 1)[0]}"
            else:
                extra = ""
            print(f"[OK] proxies={len(source_found)} source={source['name']}{extra}")
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
    for match in re.finditer(r"https?://[^\s\"'`<>\]\|)]+", text, re.I):
        raw = match.group(0).split("`")[0].rstrip(").,;\"'|")
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
    if page_url:
        for match in re.finditer(
            r"""(?:href|src)=["']([^"']+\.(?:yaml|yml|txt|json)(?:[?#][^"']*)?)["']""",
            text,
            re.I,
        ):
            link = urljoin(page_url, html.unescape(match.group(1)))
            if not link.startswith("http"):
                continue
            if exclude_keyword and exclude_keyword in link.lower():
                continue
            files.append((_score_sub_link(link, match.group(0), prefer=prefer), link))
    files.sort(key=lambda item: item[0], reverse=True)
    bare.sort(key=lambda item: item[0], reverse=True)
    # 有扩展名链接只扫扩展名；没有才扫裸链接
    chosen = files if files else bare
    return unique_ordered([url for _, url in chosen])


def discover_sublink(page_url: str, prefer: str = "", exclude: str = "") -> list[str]:
    global _DISCOVER_PAGES
    page_url = _blob_to_raw(page_url.strip())
    _DISCOVER_PAGES = [page_url]
    print(f"[INFO] sublink try page: {page_url}")
    try:
        body = fetch_text(page_url)
    except Exception as exc:
        print(f"[WARN] sublink page failed: {page_url} {exc}")
        return []
    candidate_links = _collect_sub_links(body, page_url, prefer=prefer, exclude=exclude)
    if not candidate_links:
        print(f"[WARN] sublink discovery failed: {page_url}")
        return []
    return candidate_links


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
_TOOLKIT_ARCHIVE_URL = ""
_DISCOVER_PAGES: list[str] = []


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


def _find_local_package(name: str) -> Path | None:
    raw = str(name or "").strip().strip("\"'")
    if not raw or re.match(r"https?://", raw, re.I):
        return None
    path = Path(raw).expanduser()
    if path.is_file():
        return path.resolve()
    filename = path.name
    if not filename:
        return None
    seen: set[str] = set()
    for base in _path_search_bases():
        for folder in (base, base / "output", base / "history"):
            key = str(folder)
            if key in seen:
                continue
            seen.add(key)
            candidate = folder / filename
            if candidate.is_file():
                return candidate.resolve()
    return None


def _toolkit_kind(url: str) -> str:
    if _find_local_package(url):
        return "local"
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
    listing = ""
    try:
        listing = fetch_text(list_url)
        if list_url.rstrip("/") != page_url.rstrip("/"):
            print(f"[INFO] toolkit try page: {list_url}")
    except Exception:
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
    if "latest" not in seen_tags and not token:
        tags.append((1, "latest"))
    tags.sort(key=lambda item: item[0], reverse=True)
    ranked: list[tuple[int, str]] = []
    seen: set[str] = set()
    for _, tag in tags:
        asset_page = f"https://github.com/{owner}/{repo}/releases/expanded_assets/{tag}"
        try:
            body = fetch_text(asset_page)
        except Exception:
            continue
        print(f"[INFO] toolkit try page: {asset_page}")
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
    local = _find_local_package(url)
    if local is not None:
        print(f"[OK] toolkit using local: {local} bytes={local.stat().st_size}")
        return local
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
            for attempt in range(1, 4):
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
                        total = int(response.headers.get("Content-Length") or 0)
                        with dest.open("wb") as handle:
                            for chunk in response.iter_content(chunk_size=1024 * 256):
                                if not chunk:
                                    continue
                                handle.write(chunk)
                                written += len(chunk)
                    if total and written < total:
                        raise RuntimeError(f"incomplete download {written}/{total}")
                    downloaded = True
                    break
                except Exception as exc:
                    last_error = exc
                    dest.unlink(missing_ok=True)
                    print(f"[WARN] toolkit download retry {attempt}/3: {exc}")
                    time.sleep(attempt)
            if downloaded:
                break
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


_NESTED_PKG_SUFFIX = {".apk", ".xapk", ".apks", ".aab", ".xpi", ".crx"}
# Runtime / asset files that never hold APK config keys or subscribe URLs.
_APK_SKIP_SO = {
    "libflutter.so",
    "libgojni.so",
    "libhysteria2.so",
    "libhev-socks5-tunnel.so",
    "libtun2socks.so",
    "libmmkv.so",
    "libverificationlib.so",
    "libdatastore_shared_counter.so",
    "libimage_processing_util_jni.so",
    "libsurface_util_jni.so",
}


def _looks_like_zip(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"PK\x03\x04"
    except Exception:
        return False


def _is_nested_package(path: Path) -> bool:
    if not path.is_file():
        return False
    suffix = path.suffix.lower()
    if path.stat().st_size < 256 * 1024:
        return False
    if suffix in _NESTED_PKG_SUFFIX:
        return _looks_like_zip(path) or suffix in {".apk", ".xapk", ".apks", ".aab"}
    if suffix not in {"", ".zip", ".bin"}:
        return False
    if not _looks_like_zip(path):
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            names = [item.filename.lower() for item in zf.infolist()[:80]]
    except Exception:
        return False
    return any(
        name.endswith("androidmanifest.xml")
        or name.endswith("libapp.so")
        or "/libapp.so" in name
        or name.endswith("classes.dex")
        or name.endswith(".apk")
        for name in names
    )


def _nested_apk_paths(dest_dir: Path) -> list[Path]:
    found: list[Path] = []
    nested_root = dest_dir / "_nested"
    for path in dest_dir.rglob("*"):
        if nested_root in path.parents or path == nested_root:
            continue
        if not _is_nested_package(path):
            continue
        found.append(path)
    found.sort(key=lambda item: (item.stat().st_size, item.name.lower()), reverse=True)
    return found


def _extract_nested_packages(dest_dir: Path, depth: int = 0) -> list[str]:
    if depth >= 3:
        return []
    unpacked: list[str] = []
    nested_root = dest_dir / "_nested"
    for path in _nested_apk_paths(dest_dir):
        target = nested_root / f"{depth}-{path.stem}"
        if target.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        if not _extract_archive(path, target):
            shutil.rmtree(target, ignore_errors=True)
            continue
        unpacked.append(path.name)
        unpacked.extend(_extract_nested_packages(target, depth + 1))
        try:
            path.unlink()
        except Exception:
            pass
    return unpacked


def _zip_member_keep(filename: str, size: int, apk_mode: bool = False) -> bool:
    low = filename.replace("\\", "/").lower()
    base = low.rsplit("/", 1)[-1]
    if base in _APK_SKIP_SO:
        return False
    if base.endswith(".so") and "libapp" not in base:
        return False
    if base.endswith(".dex") or "libapp" in base:
        return True
    suffix = Path(base).suffix
    if suffix in _NESTED_PKG_SUFFIX and size >= 256 * 1024:
        if base.startswith("config.") and "arm64" not in base:
            return False
        return True
    if apk_mode:
        return False
    if suffix in _TOOLKIT_TEXT_EXT:
        return True
    return False


def _extract_zip_filtered(zf: Any, dest_dir: Path, apk_mode: bool = False) -> bool:
    members = [
        info for info in zf.infolist()
        if not info.is_dir() and _zip_member_keep(info.filename, info.file_size, apk_mode)
    ]
    if not members:
        zf.extractall(dest_dir)
        return True
    for info in members:
        zf.extract(info, dest_dir)
    return True


def _extract_archive(archive: Path, dest_dir: Path) -> bool:
    name = archive.name.lower()
    try:
        if name.endswith(".crx"):
            archive = _unwrap_crx(archive)
            name = archive.name.lower()
        if name.endswith((".zip", ".apk", ".xapk", ".apks", ".xpi", ".crx")):
            import zipfile
            with zipfile.ZipFile(archive) as zf:
                apk_mode = name.endswith((".apk", ".xapk", ".apks", ".aab"))
                return _extract_zip_filtered(zf, dest_dir, apk_mode=apk_mode)
        if name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz"):
            import tarfile
            with tarfile.open(archive) as tf:
                tf.extractall(dest_dir)
            return True
        if name.endswith(".7z"):
            seven = _have_7z_tool()
            if seven:
                result = subprocess.run(
                    [seven, "x", str(archive), f"-o{dest_dir}", "-y"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
                raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "7z failed")
            try:
                import py7zr
            except ImportError as exc:
                print(f"[WARN] toolkit py7zr missing: {exc}")
                return False
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
            seven = _have_7z_tool()
            if seven:
                result = subprocess.run(
                    [seven, "x", str(archive), f"-o{dest_dir}", "-y"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
            unrar = _which_any("unrar", "unar", "rar")
            if unrar:
                result = subprocess.run(
                    [unrar, "x", "-o+", str(archive), str(dest_dir) + "/"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return True
            try:
                import rarfile
            except ImportError as exc:
                print(f"[WARN] toolkit rarfile missing: {exc}")
                return False
            with rarfile.RarFile(archive) as rf:
                rf.extractall(dest_dir)
            return True
        seven = _have_7z_tool()
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
        nodes = extract_proxies(text)
        if nodes:
            found.extend(nodes)
    return found


def _toolkit_path_parts(path: str) -> list[str]:
    return [p for p in str(path or "").split("/") if p]


def _toolkit_tail_parts(path: str) -> list[str]:
    parts = _toolkit_path_parts(path)
    return parts[-6:] if len(parts) > 6 else parts


def _unwrap_proxy_url(url: str) -> str:
    raw = str(url).split("?", 1)[0]
    match = re.match(
        r"https?://(?:ghfast\.top|ghproxy\.[^/]+|mirror\.ghproxy\.com)/+(https?://.+)$",
        raw,
        re.I,
    )
    return match.group(1) if match else raw


def _url_tokens(url: str) -> list[str]:
    raw = _unwrap_proxy_url(url)
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    parts = [p for p in parsed.path.split("/") if p]
    if "jsdelivr.net" in host and len(parts) >= 3 and parts[0].lower() == "gh":
        user = parts[1]
        repo_ref = parts[2]
        if "@" in repo_ref:
            repo, ref = repo_ref.split("@", 1)
        else:
            repo, ref = repo_ref, "main"
        return ["github", user, repo, ref, *parts[3:]]
    if host == "raw.githubusercontent.com" and len(parts) >= 3:
        user, repo, *rest = parts
        if len(rest) >= 3 and rest[0] == "refs" and rest[1] == "heads":
            ref, rest = rest[2], rest[3:]
        else:
            ref, rest = rest[0], rest[1:]
        return ["github", user, repo, ref, *rest]
    if host == "github.com" and len(parts) >= 4 and parts[2] == "raw":
        user, repo = parts[0], parts[1]
        rest = parts[3:]
        if len(rest) >= 3 and rest[0] == "refs" and rest[1] == "heads":
            ref, rest = rest[2], rest[3:]
        else:
            ref, rest = (rest[0] if rest else "main"), rest[1:]
        return ["github", user, repo, ref, *rest]
    if "gitlab." in host or host.endswith("gitlab.com"):
        flat: list[str] = []
        index = 0
        while index < len(parts):
            if parts[index] == "-" and index + 1 < len(parts) and parts[index + 1] == "raw":
                index += 2
                continue
            flat.append(parts[index])
            index += 1
        return [host, *flat]
    return [host, *parts]


def _url_filename(url: str) -> str:
    parts = _url_tokens(url)
    return parts[-1].lower() if parts else ""


def _url_group_key(url: str) -> str:
    name = _url_filename(url)
    return re.sub(r"\d+", "#", name) if name else urlparse(_unwrap_proxy_url(url)).netloc.lower()


def _aggregate_urls(urls: list[str]) -> str:
    items = unique_ordered([str(item).split("?", 1)[0] for item in urls if item])
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    rows = [_url_tokens(item) for item in items]
    prefix: list[str] = []
    for column in zip(*rows):
        unique = list(dict.fromkeys(column))
        if len(unique) != 1:
            break
        prefix.append(unique[0])
    suffix: list[str] = []
    mids = [row[len(prefix):] for row in rows]
    while mids and all(item and item[-1] == mids[0][-1] for item in mids):
        suffix.insert(0, mids[0][-1])
        for item in mids:
            item.pop()
    def _finish(parts: list[str]) -> str:
        rendered = [item for item in parts if item]
        if rendered and rendered[0] == "github":
            hosts = unique_ordered(
                [urlparse(_unwrap_proxy_url(item)).netloc for item in items]
            )
            rendered[0] = hosts[0] if len(hosts) == 1 else "{" + "|".join(hosts) + "}"
        return "https://" + "/".join(rendered)

    if mids and all(len(item) == len(mids[0]) and item for item in mids):
        rendered = list(prefix)
        for index in range(len(mids[0])):
            unique = list(dict.fromkeys(item[index] for item in mids))
            rendered.append(unique[0] if len(unique) == 1 else "{" + "|".join(unique) + "}")
        return _finish(rendered + suffix)
    mid_text = unique_ordered(["/".join(item) for item in mids if item])
    if not mid_text:
        return _finish(prefix + suffix)
    if len(mid_text) == 1:
        return _finish(prefix + mid_text + suffix)
    return _finish(prefix + ["{" + "|".join(mid_text) + "}"] + suffix)


def _toolkit_format_group(urls: list[str]) -> str:
    return _aggregate_urls(urls)


def _print_toolkit_groups(hits: list[tuple[str, list[str], int]]) -> None:
    embedded = [row for row in hits if str(row[0]).startswith("embedded:")]
    remote = [row for row in hits if not str(row[0]).startswith("embedded:")]
    if embedded:
        marks = [mark for _, group, _ in embedded for mark in group]
        new_total = sum(new for _, _, new in embedded)
        print(f"[OK] proxies={len(set(marks))} new={new_total} embedded=archive-config")
    buckets: dict[tuple[str, int], list[tuple[str, list[str], int]]] = {}
    order: list[tuple[str, int]] = []
    for url, marks, new in remote:
        depth = len(_url_tokens(url))
        key = (_url_group_key(url) or url, depth)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append((url, marks, new))
    for key in order:
        rows = buckets[key]
        marks = [mark for _, group, _ in rows for mark in group]
        new_total = sum(new for _, _, new in rows)
        label = _aggregate_urls([url for url, _, _ in rows])
        print(f"[OK] proxies={len(set(marks))} new={new_total} url={label}")


def _collect_toolkit_candidates(page_url: str, prefer: str = "") -> list[str]:
    kind = _toolkit_kind(page_url)
    if kind == "probe":
        kind = _probe_payload(page_url)
    print(f"[INFO] toolkit try {kind}: {page_url}")
    if kind == "local":
        found = _find_local_package(page_url)
        return [str(found)] if found else []
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
    global _TOOLKIT_EMBEDDED, _TOOLKIT_ARCHIVE_URL
    _TOOLKIT_EMBEDDED = []
    _TOOLKIT_ARCHIVE_URL = ""
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
            nested = _extract_nested_packages(unpack)
            if nested:
                print(f"[INFO] toolkit nested unpacked={len(nested)}")
            embedded = _collect_toolkit_embedded_proxies(unpack)
            urls = _collect_toolkit_sub_urls(unpack)
            if embedded:
                _TOOLKIT_EMBEDDED = embedded
                print(f"[OK] toolkit embedded proxies={len(embedded)} archive={archive.name}")
            if urls:
                print(f"[OK] toolkit discovered subs={len(urls)} archive={archive.name}")
            if embedded or urls:
                _TOOLKIT_ARCHIVE_URL = archive_url
                return urls
            print(f"[WARN] toolkit empty bundle: {archive.name}")
        print(f"[WARN] toolkit discovery failed: {page_url}")
        return []
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 16 or data[-pad:] != bytes([pad]) * pad:
        return data
    return data[:-pad]


def _aes128_cbc(key: bytes, data: bytes, iv: bytes) -> bytes:
    blob = data[: len(data) - (len(data) % 16)]
    if len(blob) < 32:
        raise RuntimeError("ciphertext too short")
    if len(iv) != 16:
        iv = (iv + b"\x00" * 16)[:16]
    try:
        from Crypto.Cipher import AES

        return AES.new(key, AES.MODE_CBC, iv).decrypt(blob)
    except Exception:
        pass
    proc = subprocess.run(
        [
            "openssl",
            "enc",
            "-aes-128-cbc",
            "-d",
            "-K",
            key.hex(),
            "-iv",
            iv.hex(),
            "-nopad",
        ],
        input=blob,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout
    raise RuntimeError("AES decrypt unavailable (install pycryptodome or openssl)")


def _aes128_cbc_zero_iv(key: bytes, data: bytes) -> bytes:
    return _aes128_cbc(key, data, b"\x00" * 16)


_APK_KEY_PREFIX_DENY = (
    b"get", b"set", b"hash", b"parse", b"encode", b"decode", b"write",
    b"compute", b"game", b"uint", b"chacha", b"iso7", b"numpad", b"idle",
    b"main", b"also", b"hint", b"chunk",
)
_APK_KEY_CTX = (b"aes", b"ecfg", b"sare", b"secret", b"cfg")


def _apk_scan_file(path: Path) -> bool:
    low_name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".dex" or "libapp" in low_name:
        return path.stat().st_size <= 32 * 1024 * 1024
    return False


def _apk_key_shape(item: bytes) -> int:
    """Score password-like 16-byte keys shared by old/new Play packages.

    Both families are [A-Za-z0-9]{16} with upper+lower+digit, 12+ unique
    chars, 2-6 digits, and do not look like CamelCase API identifiers.
    """
    if len(item) != 16 or not item.isalnum():
        return 0
    upper = sum(65 <= b <= 90 for b in item)
    lower = sum(97 <= b <= 122 for b in item)
    digit = sum(48 <= b <= 57 for b in item)
    if not upper or not lower or not digit:
        return 0
    if digit < 2 or digit > 6:
        return 0
    unique = len(set(item))
    if unique < 12:
        return 0
    low = item.lower()
    if any(low.startswith(prefix) for prefix in _APK_KEY_PREFIX_DENY):
        return 0
    # Java/Kotlin identifiers: isSamsung..., bufferInt..., times2ToThe..., Extensions...
    if re.match(rb"^[a-z]{2,}[A-Z]", item):
        return 0
    if re.match(rb"^[a-z]{3,}\d+[A-Z]", item):
        return 0
    if re.match(rb"^[A-Z][a-z]{4,}", item):
        return 0
    score = 8 + unique - 12
    # old 8Yfi... starts with digit; new d3JV... starts with lowercase
    if 48 <= item[0] <= 57 or 97 <= item[0] <= 122:
        score += 3
    if 5 <= upper <= 8 and 5 <= lower <= 9:
        score += 2
    return score


def _apk_scan(root: Path) -> tuple[list[str], list[str], list[bytes], list[str]]:
    prefixes: list[str] = []
    names: list[str] = []
    tokens: list[str] = []
    scored: list[tuple[int, bytes]] = []
    for path in root.rglob("*"):
        if not path.is_file() or not _apk_scan_file(path):
            continue
        try:
            blob = path.read_bytes()
        except Exception:
            continue
        low_name = path.name.lower()
        for match in re.finditer(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%\-]+", blob):
            url = match.group(0).decode("ascii", "ignore").rstrip("\\").rstrip()
            low = url.lower()
            host = urlparse(url.split("?", 1)[0]).netloc
            if "." not in host or host.count(".") < 1:
                continue
            if any(mark in low for mark in (
                "/config/", "/raw/data/", "/data/",
                "gitee.com/api/v5/repos", "foxovpn", "159236", "ecsfg",
                "onmicrosoft", "jsdelivr", "shadowsharing", "v2gh",
            )):
                piece = url.split("?", 1)[0]
                for mark in ("/config", "/data", "/raw/data"):
                    idx = piece.lower().find(mark)
                    if idx != -1:
                        prefixes.append(piece[: idx + len(mark)])
                        break
                else:
                    prefixes.append(piece.rsplit("/", 1)[0])
        for match in re.finditer(
            rb"(?:ecfg(?:\d+)?(?:_[a-z]{2})?|sareserver(?:\d+)?(?:_[a-z]{2})?|socks5)",
            blob,
        ):
            names.append(match.group(0).decode("ascii", "ignore"))
        for match in re.finditer(rb"access_token=([0-9a-f]{32})", blob):
            tokens.append(match.group(1).decode("ascii"))
        libapp = "libapp" in low_name
        # Flutter AOT one-byte string of length 16 is tagged 0xA0.
        for match in re.finditer(rb"\xa0([A-Za-z0-9]{16})", blob):
            item = match.group(1)
            shape = _apk_key_shape(item)
            if not shape:
                continue
            bonus = 40 + shape
            if libapp:
                bonus += 8
            after = blob[match.end(): match.end() + 12]
            # leftover old key still sits next to "servers" in new SS builds
            if after.startswith(b"servers") or after[1:8] == b"servers":
                bonus -= 6
            scored.append((bonus, item))
        # DEX MUTF-8 string: uleb128(16) == 0x10, payload, NUL
        for match in re.finditer(rb"\x10([A-Za-z0-9]{16})\x00", blob):
            item = match.group(1)
            shape = _apk_key_shape(item)
            if not shape:
                continue
            bonus = 28 + shape
            window = blob[max(0, match.start() - 48): match.end() + 48].lower()
            if any(mark in window for mark in _APK_KEY_CTX):
                bonus += 3
            scored.append((bonus, item))
        for match in re.finditer(rb"(?:[A-Za-z0-9]\x00){16}", blob):
            item = match.group(0)[::2]
            shape = _apk_key_shape(item)
            if not shape:
                continue
            bonus = 12 + shape
            window = blob[max(0, match.start() - 48): match.end() + 48].lower()
            if any(mark in window for mark in _APK_KEY_CTX):
                bonus += 3
            scored.append((bonus, item))
    ranked: list[bytes] = []
    seen: set[bytes] = set()
    for _score, item in sorted(scored, key=lambda pair: pair[0], reverse=True):
        if item in seen:
            continue
        seen.add(item)
        ranked.append(item)
        if len(ranked) >= 12:
            break
    return unique_ordered(prefixes), unique_ordered(names), ranked, unique_ordered(tokens)[:8]


def _apk_keys_from_source(source: dict[str, Any]) -> list[bytes]:
    raw = source.get("keys")
    if raw is None:
        return []
    if isinstance(raw, (bytes, bytearray)):
        items = [bytes(raw)]
    elif isinstance(raw, str):
        items = [raw.encode("utf-8")]
    else:
        items = []
        for item in raw:
            if isinstance(item, (bytes, bytearray)):
                items.append(bytes(item))
            else:
                items.append(str(item).encode("utf-8"))
    return items


def _apk_keys_for(source: dict[str, Any], scanned: list[bytes] | None = None) -> list[bytes]:
    merged: list[bytes] = []
    seen: set[bytes] = set()
    for item in list(scanned or []):
        if item in seen or len(item) not in {16, 24, 32}:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _apk_build_cfg_urls(prefixes: list[str], names: list[str], tokens: list[str]) -> list[str]:
    urls: list[str] = []
    for prefix in prefixes:
        base = prefix.rstrip("/")
        last = base.rsplit("/", 1)[-1]
        if "." in last or last.lower().startswith(("ecfg", "sare", "socks")):
            urls.append(base)
        for name in names:
            piece = f"{base}/{name}"
            if "access_token=" in piece.lower():
                urls.append(piece)
            elif "gitee.com" in base.lower() and tokens:
                for token in tokens:
                    urls.append(f"{piece}?access_token={token}")
            else:
                urls.append(piece)
    built = unique_ordered(urls)
    extra = [_safe_http_url(item) for item in built if "@" in item]
    return unique_ordered(built + extra)


def _apk_decrypt_once(
    raw: bytes,
    key: bytes,
    iv: bytes,
    skip: int,
    do_unpad: bool,
) -> str:
    plain = _aes128_cbc(key, raw, iv)
    if skip:
        plain = plain[skip:] if len(plain) > skip else plain
    if do_unpad:
        plain = _pkcs7_unpad(plain)
    text = plain.decode("utf-8", errors="replace").strip()
    if text and "://" not in text.split("\n", 1)[0]:
        text = "ss://" + text.lstrip()
    if text.count("://") < 3:
        raise RuntimeError("plain has no uri")
    return text


def _apk_decrypt_body(
    body: str,
    keys: list[bytes],
    locked: tuple[bytes, bytes, int, bool] | None = None,
) -> tuple[str, tuple[bytes, bytes, int, bool]]:
    compact = "".join(str(body).split())
    raw = base64.b64decode(compact)
    zero = b"\x00" * 16
    if locked:
        return _apk_decrypt_once(raw, *locked), locked
    last_error = "no key"
    for key in keys:
        if len(key) not in {16, 24, 32}:
            continue
        for iv, skip, do_unpad in ((key, 0, True), (zero, 16, False), (zero, 0, True)):
            try:
                text = _apk_decrypt_once(raw, key, iv, skip, do_unpad)
            except Exception as exc:
                last_error = str(exc)
                continue
            return text, (key, iv, skip, do_unpad)
    raise RuntimeError(last_error)


def _discover_toolkit_encrypted_apk(
    kind: str,
    source: dict[str, Any],
    page_url: str,
    name_order: list[str],
) -> tuple[list[dict[str, Any]], str]:
    page_url = page_url.strip()
    label = f"toolkit {kind}"
    if not page_url:
        print(f"[WARN] {label} missing url")
        return [], ""
    prefer = str(source.get("prefer") or "apk")
    ua = str(source.get("user_agent") or "v2rayNG")
    referer = str(source.get("referer") or "")
    archives = unique_ordered(_collect_toolkit_candidates(page_url, prefer=prefer))[:1]
    if not archives:
        print(f"[WARN] {label} no archive url page={page_url}")
        return [], ""
    work = Path(tempfile.mkdtemp(prefix=f"{kind}-"))
    tried = 0
    last_err = ""
    try:
        for archive_url in archives:
            archive = _download_archive(archive_url, work)
            if not archive:
                continue
            unpack = work / "unpack"
            os.makedirs(str(unpack), exist_ok=True)
            if not _extract_archive(archive, unpack):
                continue
            nested = _extract_nested_packages(unpack)
            if nested:
                print(f"[INFO] toolkit nested unpacked={len(nested)}")
            prefixes, names, scanned, tokens = _apk_scan(unpack)
            hard_keys = _apk_keys_for(source, scanned)
            print(
                f"[INFO] {label} scanned prefixes={len(prefixes)} "
                f"files={len(names)} keys={len(hard_keys)} archive={archive.name}"
            )
            if not prefixes:
                continue
            wanted = [item.lower() for item in name_order]

            def _name_rank(item: str) -> tuple[int, int, int]:
                low = str(item).lower()
                if low in wanted:
                    return (0, wanted.index(low), -len(low))
                return (1, 99, -len(low))

            names = sorted(names, key=_name_rank)
            urls = _apk_build_cfg_urls(prefixes, names, tokens)
            urls.sort(
                key=lambda item: (
                    0 if "shadowrockets.app" in item.lower() else
                    1 if "pixelor" in item.lower() else
                    2 if "159236" in item.lower() else
                    3 if "onmicrosoft" in item.lower() or "jsdelivr" in item.lower() else 4,
                    next(
                        (
                            wanted.index(item.lower().rsplit("/", 1)[-1].split("?", 1)[0])
                            for _ in [0]
                            if item.lower().rsplit("/", 1)[-1].split("?", 1)[0] in wanted
                        ),
                        99,
                    ),
                )
            )
            collected: list[dict[str, Any]] = []
            seen: set[str] = set()
            locked = None
            hit_names: set[str] = set()
            key_pool = list(hard_keys)
            used_scan = False
            last_err = ""
            tried = 0
            apk_hits: list[tuple[str, list[str], int]] = []
            def _fetch_cfg(url: str) -> tuple[str, str | None, str]:
                try:
                    body = fetch_text(
                        url,
                        retries=CFG_FETCH_RETRIES,
                        user_agent=ua,
                        referer=referer,
                        timeout=CFG_FETCH_TIMEOUT,
                    )
                    return url, body, ""
                except Exception as exc:
                    return url, None, str(exc)

            workers = max(1, min(CFG_FETCH_WORKERS, len(urls)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_fetch_cfg, url) for url in urls]
                for future in as_completed(futures):
                    url, body, err = future.result()
                    short = url.split("?", 1)[0]
                    fname = short.rsplit("/", 1)[-1].lower()
                    tried += 1
                    if err or body is None:
                        last_err = err or "empty"
                        continue
                    try:
                        plain, locked = _apk_decrypt_body(body, key_pool, locked)
                    except Exception as exc:
                        last_err = str(exc)
                        if used_scan or not scanned:
                            continue
                        used_scan = True
                        key_pool = _apk_keys_for(source, scanned)
                        try:
                            plain, locked = _apk_decrypt_body(body, key_pool, None)
                        except Exception as exc:
                            last_err = str(exc)
                            continue
                    found = extract_proxies(plain)
                    if not found:
                        continue
                    kept: list[dict[str, Any]] = []
                    marks: list[str] = []
                    for proxy in found:
                        mark = proxy_fingerprint(proxy)
                        marks.append(mark)
                        if mark in seen:
                            continue
                        seen.add(mark)
                        kept.append(proxy)
                    apk_hits.append((short, marks, len(kept)))
                    collected.extend(kept)
                    hit_names.add(fname)
            if collected:
                _print_toolkit_groups(apk_hits)
                return collected, archive_url
        extra = f" tried={tried}"
        if last_err:
            extra += f" last={last_err[:80]}"
        print(f"[WARN] {label} discovery failed{extra}")
        return [], ""
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _discover_toolkit_sr_apk(source: dict[str, Any], page_url: str) -> tuple[list[dict[str, Any]], str]:
    return _discover_toolkit_encrypted_apk(
        "sr-apk",
        source,
        page_url,
        ["ecfg6_zh", "ecfg_zh", "ecfg6_en", "ecfg6", "ecfg5", "ecfg"],
    )


def _discover_toolkit_ss_apk(source: dict[str, Any], page_url: str) -> tuple[list[dict[str, Any]], str]:
    return _discover_toolkit_encrypted_apk(
        "ss-apk",
        source,
        page_url,
        ["sareserver6_en", "sareserver_en", "sareserver6", "sareserver", "socks5"],
    )


def discover_article(feed_url: str, prefer: str = "") -> list[str]:
    global _DISCOVER_PAGES
    _DISCOVER_PAGES = []
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

        stamped = [(entry_stamp(entry), entry) for entry in parsed.entries[:30]]
        latest = max((stamp for stamp, _ in stamped if stamp != "00000000"), default="")
        if latest:
            pages = [
                str(getattr(entry, "link", "") or "")
                for stamp, entry in stamped
                if stamp == latest
            ]
        else:
            pages = [str(getattr(stamped[0][1], "link", "") or "")] if stamped else []
        pages = [page for page in pages if page]
        if pages:
            via_feed = True
            print(f"[INFO] article try feed: {feed_url} date={latest or 'latest'}")
    if not pages and body:
        raw_pages = _collect_article_links(body, feed_url)
        stamped_pages = [(_page_stamp(page), page) for page in raw_pages]
        latest = max((stamp for stamp, _ in stamped_pages if stamp != "00000000"), default="")
        if latest:
            pages = [page for stamp, page in stamped_pages if stamp == latest]
        else:
            pages = sorted(raw_pages, key=_page_stamp, reverse=True)[:1]
        if pages:
            print(f"[INFO] article try page: {feed_url} date={latest or 'latest'}")

    collected: list[str] = []
    pages = unique_ordered(pages)
    if not pages:
        print(f"[WARN] article discovery failed: {feed_url}")
        return []

    def _page_subs(page: str) -> list[str]:
        try:
            return discover_sublink(page, prefer=prefer)
        except Exception:
            return []

    workers = max(1, min(CFG_FETCH_WORKERS, len(pages)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_page_subs, page) for page in pages]
        for future in as_completed(futures):
            collected.extend(future.result() or [])
    found = unique_ordered(collected)
    _DISCOVER_PAGES = list(pages)
    if not found:
        print(f"[WARN] article discovery failed: {feed_url}")
    return found


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
        _DROP_NAMES.append(str(bad.get("name") or ""))
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
        global _DROP_NAMES
        _DROP_NAMES = []
        metrics = _benchmark_batch(
            engine, temp_dir, config_path, controller_url, controller_port, list(proxies)
        )
        if _DROP_NAMES:
            names = " | ".join(item for item in _DROP_NAMES if item)
            if len(names) > 400:
                names = names[:397] + "..."
            print(f"[DROP] discarded={len(_DROP_NAMES)} {names}")
        _DROP_NAMES = []
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
            except Exception:
                _DROP_NAMES.append(str(proxy.get("name") or ""))
                continue
            if metric:
                metrics.append(metric)
            if completed % 100 == 0 or completed == len(futures):
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


def limit_metrics_total(metrics: list[ProxyMetric]) -> list[ProxyMetric]:
    if len(metrics) <= MAX_LIVE_TOTAL:
        return metrics
    print(
        f"[INFO] cap live total from {len(metrics)} to {MAX_LIVE_TOTAL} trim large sources first"
    )
    global _SEP_JUST_PRINTED
    _SEP_JUST_PRINTED = False
    grouped: dict[str, list[ProxyMetric]] = {}
    order: list[str] = []
    for item in metrics:
        key = source_prefix_of(str(item.proxy.get("name") or ""))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(item)
    for key in grouped:
        grouped[key].sort(key=lambda item: item.health_score)
    need = len(metrics) - MAX_LIVE_TOTAL
    floor = 5
    while need > 0:
        candidates = [key for key in order if len(grouped[key]) > floor]
        if not candidates:
            if floor <= 0:
                break
            floor -= 1
            continue
        key = max(candidates, key=lambda item: len(grouped[item]))
        grouped[key].pop(0)
        need -= 1
    kept: list[ProxyMetric] = []
    for key in order:
        kept.extend(grouped[key])
    return kept


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
    metrics = limit_metrics_total(metrics)
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