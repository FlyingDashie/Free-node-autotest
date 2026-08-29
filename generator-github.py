from __future__ import annotations

import base64
import gzip
import hashlib
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse, parse_qs

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

SOURCE_GROUPS = [
    {
        "name": "大FQ运动",
        "primary": "https://raw.githubusercontent.com/hello-world-1989/cn-news/refs/heads/main/clash.yaml",
        "fallbacks": [],
        "prefix": "[大FQ运动] ",
    },
    {
        "name": "大FQ运动-官网",
        "primary": "https://end-gfw.com/ss-key",
        "fallbacks": [
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together-ss",
            "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together",
        ],
        "prefix": "[大FQ运动-官网] ",
    },
    {
        "name": "ChromeGO",
        "primary": "https://chg26.makou.cc.cd/",
        "fallbacks": [],
        "prefix": "[ChromeGO] ",
    },
    {
        "name": "V2Rayshare-RSS",
        "primary": "discover:v2rayshare",
        "fallbacks": [],
        "prefix": "[V2Rayshare-RSS] ",
    },
    {
        "name": "OpenRunner-RSS",
        "primary": "discover:openrunner",
        "fallbacks": [
            "https://raw.githubusercontent.com/openRunner/clash-freenode/main/sub.yaml",
            "https://raw.githubusercontent.com/openRunner/clash-freenode/main/clash.yaml",
            "https://raw.githubusercontent.com/openrunner/clash-freenode/main/clash.yaml",
        ],
        "prefix": "[OpenRunner-RSS] ",
    },
    {
        "name": "Mibei77-RSS",
        "primary": "discover:mibei77",
        "fallbacks": [],
        "prefix": "[Mibei77-RSS] ",
    },
    {
        "name": "Yoyapai-RSS",
        "primary": "discover:yoyapai",
        "fallbacks": [],
        "prefix": "[Yoyapai-RSS] ",
    },
    {
        "name": "V2rayclashfree-RSS",
        "primary": "discover:v2rayclashfree",
        "fallbacks": [],
        "prefix": "[V2rayclashfree-RSS] ",
    },
    {
        "name": "Free-clash-v2ray-README",
        "primary": "discover:free-clash-v2ray",
        "fallbacks": [
            "https://free-clash-v2ray.github.io/uploads/latest.yaml",
        ],
        "prefix": "[Free-clash-v2ray] ",
    },
    {
        "name": "FreeV2-Base64",
        "primary": "https://xmxosfepggzm.503403.xyz",
        "fallbacks": [],
        "prefix": "[FreeV2-Base64] ",
    },
    {
        "name": "Pawdroid-Base64",
        "primary": "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        "fallbacks": [
            "https://mirror.v2gh.com/https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
        ],
        "prefix": "[Pawdroid-Base64] ",
    },
    {
        "name": "V2Rayshare-订阅",
        "primary": "https://cdn.jsdelivr.net/gh/firefoxmmx2/v2rayshare_subcription/subscription/mihomo_sub.yaml",
        "fallbacks": [],
        "prefix": "[V2Rayshare-订阅] ",
    },
    {
        "name": "免费节点1",
        "primary": "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml",
        "fallbacks": [],
        "prefix": "[免费节点1] ",
    },
    {
        "name": "免费节点1-README自建",
        "primary": "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/README.md",
        "fallbacks": [
            "https://raw.githubusercontent.com/free18/v2ray/main/README.md",
        ],
        "prefix": "[免费节点1-README自建] ",
    },
    {
        "name": "免费节点2",
        "primary": "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
        "fallbacks": [],
        "prefix": "[免费节点2] ",
    },
    {
        "name": "免费节点3",
        "primary": "https://sunmiao4458.github.io/free-proxy-airport/clash.yaml",
        "fallbacks": [],
        "prefix": "[免费节点3] ",
    },
        {
        "name": "免费节点4",
        "primary": "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml",
        "fallbacks": [],
        "prefix": "[免费节点4] ",
    },
    {
        "name": "免费节点5",
        "primary": "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
        "fallbacks": [
            "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml",
        ],
        "prefix": "[免费节点5] ",
    },
    {
        "name": "免费节点6",
        "primary": "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml",
        "fallbacks": [
            "https://anaer.github.io/Sub/clash.yaml",
        ],
        "prefix": "[免费节点6] ",
    },
    {
        "name": "免费节点7",
        "primary": "https://raw.githubusercontent.com/snakem982/proxypool/main/source/clash-meta-2.yaml",
        "fallbacks": [],
        "prefix": "[免费节点7] ",
    },
    {
        "name": "免费节点8",
        "primary": "https://raw.githubusercontent.com/mahdibland/SSAggregator/master/sub/sub_merge_yaml.yml",
        "fallbacks": [],
        "prefix": "[免费节点8] ",
    },
    {
        "name": "免费节点9-1",
        "primary": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription1.yaml",
        "fallbacks": [],
        "prefix": "[免费节点9-1] ",
    },
    {
        "name": "免费节点9-2",
        "primary": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription2.yaml",
        "fallbacks": [],
        "prefix": "[免费节点9-2] ",
    },
    {
        "name": "免费节点9-3",
        "primary": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription3.yaml",
        "fallbacks": [],
        "prefix": "[免费节点9-3] ",
    },
    {
        "name": "Epodonios-v2ray-configs",
        "primary": "https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt",
        "fallbacks": [],
        "prefix": "[Epodonios-v2ray-configs] ",
    },
    {
        "name": "Clashfree-README",
        "primary": "discover:clashfree-readme",
        "fallbacks": [
            "https://raw.githubusercontent.com/free-nodes/v2rayfree/main/sub",
        "prefix": "[Clashfree-README] ",
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
}

REQUIRED_GROUPS = (
    "AUTO-FAST",
    "HK-POOL",
    "JP-POOL",
    "US-POOL",
    "AI-POOL",
    "FALLBACK",
    "PROXY",
)


@dataclass
class ProxyMetric:
    proxy: dict[str, Any]
    latency: int
    region: str
    health_score: float


def fetch_text(url: str, retries: int = MAX_RETRIES) -> str:
    headers = {
        "User-Agent": f"free-node-autotest/{VERSION} (+https://github.com/)",
        "Accept": "text/plain, text/yaml, application/yaml, */*",
        "Referer": "https://end-gfw.com/",
    }
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


def load_yaml_document(text: str) -> Any:
    try:
        return yaml.safe_load(maybe_base64_decode(text))
    except yaml.YAMLError as exc:
        print(f"[WARN] YAML document parse failed: {exc}")
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
    try:
        parsed = yaml.safe_load("proxies:\n" + "\n".join(block))
        if isinstance(parsed, dict) and isinstance(parsed.get("proxies"), list):
            return parsed["proxies"]
    except yaml.YAMLError as exc:
        print(f"[WARN] proxy block parse failed, fallback to per-line: {exc}")

    # 2. 完整解析失败时，逐行解析，只跳过坏节点
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
    if skipped:
        print(f"[WARN] skipped {skipped} invalid proxy line(s) in this source")
    return proxies


_SHARE_URI_RE = re.compile(
    r"(?:ss|ssr|vmess|vless|trojan|hysteria2?|hy2)://",
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
        chunk = re.sub(r"\s+", "", stripped[match.start():end])
        chunk = re.split(r"[<>\"']", chunk)[0]
        if "://" in chunk:
            uris.append(chunk)
    return uris


def extract_proxies(text: str) -> list[dict[str, Any]]:
    decoded = maybe_base64_decode(text)
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
        if scheme in {"vless", "trojan", "hysteria", "hysteria2", "hy2"}:
            return _parse_standard_uri(raw, scheme)
    except Exception:
        return None
    return None


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


def collect_proxies() -> tuple[int, list[dict[str, Any]]]:
    collected: list[dict[str, Any]] = []
    for source in SOURCE_GROUPS:
        source_found: list[dict[str, Any]] = []
        for url in expand_source_urls(source):
            try:
                text = fetch_text(url)
                found = extract_proxies(text)
                print(f"[OK] source={source['name']} proxies={len(found)} url={url}")
                if found:
                    prefix = source.get("prefix", "")
                    if prefix:
                        for p in found:
                            if isinstance(p, dict):
                                p["name"] = prefix + str(p.get("name", "")).strip()
                    source_found.extend(found)
                    break
            except Exception as exc:
                print(f"[WARN] source={source['name']} skipped url={url} error={exc}")
        if not source_found:
            print(f"[WARN] source={source['name']} no proxies")
            source_found = load_previous_source_proxies(source)
        print("============================================================")
        collected.extend(source_found)

    write_raw_backup(collected)
    sanitized = sanitize_and_deduplicate(collected)
    if MAX_CANDIDATES > 0 and len(sanitized) > MAX_CANDIDATES:
        print(f"[WARN] limiting candidates from {len(sanitized)} to {MAX_CANDIDATES}")
        sanitized = sanitized[:MAX_CANDIDATES]
    return len(collected), sanitized


def expand_source_urls(source: dict[str, Any]) -> list[str]:
    raw_items = [str(source["primary"])]
    raw_items.extend(str(item) for item in source.get("fallbacks", []))

    urls: list[str] = []
    for item in raw_items:
        if item == "discover:free-clash-v2ray":
            urls.extend(discover_free_clash_v2ray_urls())
        elif item == "discover:v2rayshare":
            urls.extend(discover_v2rayshare_urls())
        elif item == "discover:openrunner":
            urls.extend(discover_openrunner_urls())
        elif item == "discover:mibei77":
            urls.extend(discover_mibei77_urls())
        elif item == "discover:yoyapai":
            urls.extend(discover_yoyapai_urls())
        elif item == "discover:v2rayclashfree":
            urls.extend(discover_v2rayclashfree_urls())
        elif item == "discover:clashfree-readme":
            urls.extend(discover_clashfree_readme_urls())
        else:
            urls.append(item)
    return unique_ordered(urls)


def discover_free_clash_v2ray_urls() -> list[str]:
    readme_url = "https://raw.githubusercontent.com/free-clash-v2ray/free-clash-v2ray.github.io/main/README.md"
    print(f"[INFO] free-clash-v2ray try readme: {readme_url}")
    try:
        text = fetch_text(readme_url)
    except Exception as exc:
        print(f"[WARN] free-clash-v2ray readme failed: {exc}")
        return []

    def take(ext: str) -> list[str]:
        found = re.findall(rf"https?://[^\s\"'<>\]]+\.{ext}(?=$|[?#\s<])", text, re.I)
        def rank(u: str) -> tuple:
            name = u.split("?", 1)[0].rsplit("/", 1)[-1].lower()
            pref_3 = 0 if name.startswith("3-") else 1
            pref_meta = 0 if re.search(r"mihomo|meta", name) else 1
            return (pref_3, pref_meta, name)

        ranked = sorted(unique_ordered(found), key=rank)
        return ranked[:8]

    empty_n = fail_n = 0
    for stage, links in (("yaml", take("ya?ml")), ("txt", take("txt"))):
        for link in links:
            print(f"[INFO] free-clash-v2ray try file: {link}")
            try:
                body = fetch_text(link)
            except Exception as exc:
                print(f"[WARN] free-clash-v2ray fetch failed: {link} {exc}")
                fail_n += 1
                continue
            if not body.strip():
                print(f"[WARN] free-clash-v2ray empty file: {link}")
                empty_n += 1
                continue
            print(f"[OK] free-clash-v2ray discovered: {link}")
            return [link]
    if empty_n:
        print(f"[WARN] free-clash-v2ray discovery failed: empty subscription ({empty_n})")
    elif fail_n:
        print(f"[WARN] free-clash-v2ray discovery failed: fetch error ({fail_n})")
    else:
        print("[WARN] free-clash-v2ray discovery failed: no subscription url")
    return []


def _discover_rss_urls(site: str, spec: dict[str, Any]) -> list[str]:
    try:
        import feedparser
        from bs4 import BeautifulSoup
    except ImportError as exc:
        print(f"[WARN] {site} discovery missing dependency: {exc}")
        return []

    try:
        feed_body = fetch_text(spec["feed"])
        parsed = feedparser.parse(feed_body)
    except Exception as exc:
        print(f"[WARN] {site} feed failed: {exc}")
        return []
    if not parsed.entries:
        print(f"[WARN] {site} discovery: empty feed")
        return []

    http = urllib3.PoolManager()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def fetch_html(url: str, retries: int = 3) -> str | None:
        for _ in range(retries):
            try:
                response = http.request("get", url, headers=headers, timeout=10)
                if response.status == 200:
                    return response.data.decode("utf-8", errors="replace")
            except Exception:
                continue
        return None

    heading_names = spec.get("headings") or [r"订阅链接", r"订阅地址", r"订阅"]
    label_names = spec.get("labels") or [
        r"mihomo.{0,24}(?:订阅|配置|链接)",
        r"clash[\s\-]*meta.{0,24}(?:订阅|配置|链接)",
        r"clash.{0,24}(?:订阅|配置|链接)",
        r"v2ray.{0,24}(?:订阅|配置|链接)",
    ]
    label_priority = [
        (100, label_names[0]),
        (80, label_names[1]),
        (50, label_names[2]),
        (10, label_names[3]),
    ]
    link_re = re.compile(spec.get("link_re") or r"https?://[^\s\"'<>]+?\.(?:yaml|yml)", re.I)

    def normalize(link: str, page_url: str) -> str:
        link = "".join(str(link).split())
        if link.startswith("/"):
            from urllib.parse import urljoin
            return urljoin(page_url, link)
        return link

    def score_link(url: str, context: str = "") -> int:
        blob = f"{url} {context}".lower()
        filename = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1].lower()
        score = 1
        if "mihomo" in blob or re.fullmatch(r"m20\d{6}\.ya?ml", filename):
            score += 100
        elif re.search(r"clash\s*meta|clash-meta|meta订阅", blob):
            score += 80
        elif "clash" in blob or re.fullmatch(r"20\d{6}\.ya?ml", filename):
            score += 50
        if re.search(r"v2ray|ssr|\.txt(?:\?|$)", blob):
            score -= 80
        return score

    def collect_yaml(soup: Any, page_url: str, html: str = "") -> list[str]:
        ranked: list[tuple[int, str]] = []
        for bonus, name in label_priority:
            pat = re.compile(
                name + r"[\s:：]{0,40}(https?://[^\s\"'<>]+)",
                re.IGNORECASE,
            )
            plain = re.sub(r"<[^>]+>", " ", html or "")
            for match in pat.finditer(plain):
                raw = normalize(match.group(1), page_url)
                found = link_re.search(raw)
                if found:
                    url = found.group(0) if found.group(0).startswith("http") else raw
                    ranked.append((bonus + score_link(url, name), url))
        heading = None
        for name in heading_names:
            heading = soup.find(["h1", "h2", "h3", "h4"], string=re.compile(name))
            if heading:
                break
        scope = heading.parent if heading and heading.parent else soup
        for name in label_names:
            node = scope.find(["strong", "b", "span", "p", "h3", "h4"], string=re.compile(name))
            if not node:
                continue
            for nxt in node.find_all_next(["p", "code", "pre", "a"], limit=8):
                text = nxt.get("href") if nxt.name == "a" else nxt.get_text(" ", strip=True)
                text = normalize(text or "", page_url)
                match = link_re.search(text)
                if match:
                    url = match.group(0) if match.group(0).startswith("http") else text
                    ranked.append((score_link(url, name), url))
        for href in soup.find_all("a"):
            link = normalize(href.get("href") or "", page_url)
            match = link_re.search(link)
            if match:
                url = match.group(0) if match.group(0).startswith("http") else link
                ranked.append((score_link(url, href.get_text(" ", strip=True)), url))
        for text in soup.stripped_strings:
            compact = "".join(str(text).split())
            match = link_re.search(compact)
            if match:
                ranked.append((score_link(match.group(0), compact), match.group(0)))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return unique_ordered([url for _, url in ranked])

    def guessed_links(page_url: str) -> list[str]:
        date_match = re.search(r"(20\d{6})", page_url)
        if not date_match:
            return []
        day = date_match.group(1)
        year, month, day2 = day[:4], day[4:6], day[6:8]
        found: list[str] = []
        for tmpl in spec.get("guess") or []:
            found.append(
                tmpl.replace("{date}", day)
                .replace("{year}", year)
                .replace("{month}", month)
                .replace("{day}", day2)
            )
        return unique_ordered(found)

    txt_re = re.compile(r"https?://[^\s\"'<>\]]+?\.txt(?:$|[?#])", re.I)
    yaml_re = re.compile(r"https?://[^\s\"'<>\]]+?\.(?:yaml|yml)(?:$|[?#])", re.I)

    def blob_to_raw(link: str) -> str:
        blob = re.search(
            r"github\.com/([^/]+)/([^/]+)/(?:blob|tree)/([^/]+)/(.+)",
            link,
            re.IGNORECASE,
        )
        if blob:
            owner, repo, ref, path = blob.groups()
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        return link

    def collect_ext(soup: Any, page_url: str, html: str, ext_re: re.Pattern[str]) -> list[str]:
        ranked: list[tuple[int, str]] = []
        for href in soup.find_all("a"):
            link = normalize(href.get("href") or "", page_url)
            if ext_re.search(link.split("#")[0]):
                ranked.append((score_link(link, href.get_text(" ", strip=True)), blob_to_raw(link)))
        for match in ext_re.finditer(re.sub(r"<[^>]+>", " ", html or "")):
            ranked.append((score_link(match.group(0), ""), blob_to_raw(match.group(0))))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return unique_ordered([url for _, url in ranked])

    empty_n = 0
    fail_n = 0
    seen_files: set[str] = set()

    def probe(link: str) -> bool:
        nonlocal empty_n, fail_n
        link = blob_to_raw(link.strip())
        if link in seen_files:
            return False
        seen_files.add(link)
        print(f"[INFO] {site} try file: {link}")
        body = fetch_html(link)
        if body is None:
            print(f"[WARN] {site} fetch failed: {link}")
            fail_n += 1
            return False
        if not str(body).strip():
            print(f"[WARN] {site} empty file: {link}")
            empty_n += 1
            return False
        print(f"[OK] {site} discovered: {link}")
        return True

    for entry in parsed.entries[:10]:
        top_link = getattr(entry, "link", "")
        if not top_link:
            continue
        print(f"[INFO] {site} try page: {top_link}")
        html = fetch_html(top_link)
        if not html:
            print(f"[WARN] {site} page empty: {top_link}")
            continue
        soup = BeautifulSoup(html, "html.parser")

        yaml_cands = collect_yaml(soup, top_link, html)
        yaml_cands.extend(collect_ext(soup, top_link, html, yaml_re))
        yaml_cands = unique_ordered(yaml_cands)
        for link in yaml_cands:
            if probe(link):
                return [link]

        txt_cands = collect_ext(soup, top_link, html, txt_re)
        for link in txt_cands:
            if probe(link):
                return [link]

        for link in guessed_links(top_link):
            if probe(link):
                return [link]

    if empty_n:
        print(f"[WARN] {site} discovery failed: empty subscription ({empty_n})")
    elif fail_n:
        print(f"[WARN] {site} discovery failed: fetch error ({fail_n})")
    else:
        print(f"[WARN] {site} discovery failed: no subscription url")
    return []


def discover_v2rayshare_urls() -> list[str]:
    return _discover_rss_urls("v2rayshare", {
        "feed": "https://v2rayshare.com/feed",
        "link_re": r"https?://[^\s\"'<>]*v2rayshare[^\s\"'<>]*\.(?:yaml|yml)",
        "guess": [
            "https://static.v2rayshare.net/{year}/{month}/m{date}.yaml",
        ],
    })


def discover_openrunner_urls() -> list[str]:
    return _discover_rss_urls("openrunner", {
        "feed": "https://free.datiya.com/index.xml",
        "link_re": r"https?://[^\s\"'<>]*datiya\.com[^\s\"'<>]*\.(?:yaml|yml)|/uploads/[^\s\"'<>]+\.(?:yaml|yml)",
        "guess": [
            "https://free.datiya.com/uploads/{date}-clash.yaml",
        ],
    })


def discover_mibei77_urls() -> list[str]:
    return _discover_rss_urls("mibei77", {
        "feed": "https://www.mibei77.com/feed",
        "link_re": r"https?://[^\s\"'<>]*mibei77\.com[^\s\"'<>]*\.(?:yaml|yml)",
    })


def discover_yoyapai_urls() -> list[str]:
    found = _discover_rss_urls("yoyapai", {
        "feed": "https://yoyapai.com/feed",
        "link_re": r"https?://[^\s\"'<>]*yoyapai\.com[^\s\"'<>]*\.(?:yaml|yml)",
        "guess": [
            "https://freenode.yoyapai.com/{year}/{month}/{day}-yoyapai.com-clash-vpn-mian-fei-jiedian.yaml",
        ],
    })
    if found:
        return found

    print("[INFO] yoyapai fallback category page")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        import feedparser  # noqa: F401
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    try:
        html = requests.get(
            "https://yoyapai.com/category/mianfeijiedian",
            headers=headers,
            timeout=SOURCE_TIMEOUT,
            verify=False,
            proxies=PROXIES,
        )
        html.raise_for_status()
        soup = BeautifulSoup(html.content.decode("utf-8", "replace"), "html.parser")
    except Exception as exc:
        print(f"[WARN] yoyapai category failed: {exc}")
        return []

    posts: list[str] = []
    for href in soup.find_all("a"):
        link = str(href.get("href") or "").strip()
        if re.fullmatch(r"https://yoyapai\.com/\d+", link.rstrip("/")):
            posts.append(link.rstrip("/"))
    posts = unique_ordered(posts)[:8]
    fake_feed = "https://yoyapai.com/category/mianfeijiedian"
    class _E:
        def __init__(self, link: str) -> None:
            self.link = link
    parsed_entries = [_E(p) for p in posts]
    if not parsed_entries:
        print("[WARN] yoyapai discovery failed: no subscription url")
        return []

    # 把分类页里的文章当 RSS entries 再跑同一套抽取
    import feedparser as _fp
    parsed = _fp.FeedParserDict()
    parsed.entries = parsed_entries
    # 直接复用扫描：逐篇打开找 yaml
    http = urllib3.PoolManager()
    def fetch_html(url: str) -> str | None:
        try:
            response = http.request("get", url, headers=headers, timeout=10)
            if response.status == 200:
                return response.data.decode("utf-8", errors="replace")
        except Exception:
            return None
        return None
    link_re = re.compile(r"https?://[^\s\"'<>]*yoyapai\.com[^\s\"'<>]*\.(?:yaml|yml)", re.I)
    for post in posts:
        print(f"[INFO] yoyapai try page: {post}")
        body = fetch_html(post)
        if not body:
            continue
        for match in link_re.findall(body):
            sub = fetch_html(match)
            if sub:
                print(f"[OK] yoyapai discovered: {match}")
                return [match]
        date_match = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", body)
        if date_match:
            year = date_match.group(1)
            month = date_match.group(2).zfill(2)
            day2 = date_match.group(3).zfill(2)
            guess = f"https://freenode.yoyapai.com/{year}/{month}/{day2}-yoyapai.com-clash-vpn-mian-fei-jiedian.yaml"
            sub = fetch_html(guess)
            if sub:
                print(f"[OK] yoyapai discovered: {guess}")
                return [guess]
    print("[WARN] yoyapai discovery failed: no subscription url")
    return []


def discover_v2rayclashfree_urls() -> list[str]:
    home = "https://v2rayclashfree.com/"
    print(f"[INFO] v2rayclashfree try page: {home}")
    try:
        html = fetch_text(home)
    except Exception as exc:
        print(f"[WARN] v2rayclashfree home failed: {exc}")
        return []

    days = unique_ordered(re.findall(r"/fn/(20\d{6})\.html", html))
    days.sort(reverse=True)
    if not days:
        print("[WARN] v2rayclashfree discovery failed: no subscription url")
        return []

    empty_n = fail_n = 0

    def probe(link: str) -> bool:
        nonlocal empty_n, fail_n
        print(f"[INFO] v2rayclashfree try file: {link}")
        try:
            body = fetch_text(link)
        except Exception as exc:
            print(f"[WARN] v2rayclashfree fetch failed: {link} {exc}")
            fail_n += 1
            return False
        if not str(body).strip():
            print(f"[WARN] v2rayclashfree empty file: {link}")
            empty_n += 1
            return False
        print(f"[OK] v2rayclashfree discovered: {link}")
        return True

    for day in days[:8]:
        page = f"https://v2rayclashfree.com/fn/{day}.html"
        print(f"[INFO] v2rayclashfree try page: {page}")
        try:
            body = fetch_text(page)
        except Exception as exc:
            print(f"[WARN] v2rayclashfree page failed: {page} {exc}")
            continue
        yaml_links = unique_ordered(re.findall(r"https?://[^\s\"'<>]+\.(?:yaml|yml)", body, re.I))
        yaml_links = [u for u in yaml_links if "clash" in u.lower() or "mihomo" in u.lower() or "meta" in u.lower()] + \
                     [u for u in yaml_links if "clash" not in u.lower() and "mihomo" not in u.lower() and "meta" not in u.lower()]
        for link in unique_ordered(yaml_links):
            if probe(link):
                return [link]
        txt_links = unique_ordered(re.findall(r"https?://[^\s\"'<>]+\.txt", body, re.I))
        for link in txt_links:
            if probe(link):
                return [link]
        if probe(f"https://v2rayclashfree.com/sub/{day}-clash.yaml"):
            return [f"https://v2rayclashfree.com/sub/{day}-clash.yaml"]

    if empty_n:
        print(f"[WARN] v2rayclashfree discovery failed: empty subscription ({empty_n})")
    elif fail_n:
        print(f"[WARN] v2rayclashfree discovery failed: fetch error ({fail_n})")
    else:
        print("[WARN] v2rayclashfree discovery failed: no subscription url")
    return []


def discover_clashfree_readme_urls() -> list[str]:
    readme = "https://raw.githubusercontent.com/free-nodes/clashfree/refs/heads/main/README.md"
    print(f"[INFO] clashfree try readme: {readme}")
    try:
        text = fetch_text(readme)
    except Exception as exc:
        print(f"[WARN] clashfree readme failed: {exc}")
        return []

    found: list[str] = []
    for match in re.finditer(r"https?://[^\s\"'<>\]]+", text, re.IGNORECASE):
        link = match.group(0).rstrip(").,;\"'")
        if re.search(r"\.ya?ml(?:$|[?#])", link, re.IGNORECASE):
            found.append(link)

    urls: list[str] = []
    for link in unique_ordered(found):
        blob = re.search(
            r"github\.com/([^/]+)/([^/]+)/(?:blob|tree)/([^/]+)/(.+\.ya?ml)",
            link,
            re.IGNORECASE,
        )
        if blob:
            owner, repo, ref, path = blob.groups()
            link = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        urls.append(link)

    if not urls:
        print("[WARN] clashfree discovery failed: no .yml/.yaml link in README")
        return []

    empty: list[str] = []
    failed: list[str] = []
    ranked = sorted(
        unique_ordered(urls),
        key=lambda item: re.search(r"(20\d{6})", item).group(1) if re.search(r"(20\d{6})", item) else "",
        reverse=True,
    )
    for link in ranked:
        print(f"[INFO] clashfree try file: {link}")
        try:
            body = fetch_text(link)
        except Exception as exc:
            print(f"[WARN] clashfree fetch failed: {link} {exc}")
            failed.append(link)
            continue
        if body.strip():
            print(f"[OK] clashfree discovered: {link} bytes={len(body.encode('utf-8'))}")
            return [link]
        print(f"[WARN] clashfree empty file: {link}")
        empty.append(link)

    if empty:
        print(f"[WARN] clashfree discovery failed: empty subscription ({len(empty)})")
    elif failed:
        print(f"[WARN] clashfree discovery failed: fetch error ({len(failed)})")
    else:
        print("[WARN] clashfree discovery failed: no download url")
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


def proxy_fingerprint(proxy: dict[str, Any]) -> str:
    important = {
        "type": proxy.get("type"),
        "server": proxy.get("server"),
        "port": proxy.get("port"),
        "uuid": proxy.get("uuid"),
        "password": proxy.get("password"),
        "cipher": proxy.get("cipher"),
        "network": proxy.get("network"),
    }
    payload = json.dumps(important, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    install_dir.mkdir(parents=True, exist_ok=True)
    binary = install_dir / ("mihomo.exe" if os.name == "nt" else "mihomo")
    if binary.exists():
        print(f"[OK] using cached proxy engine: {binary}")
        return binary

    url = select_mihomo_asset()
    print(f"[INFO] downloading proxy engine: {url}")
    archive = download_file(url, install_dir)
    extracted = extract_mihomo_binary(archive, install_dir)
    extracted.chmod(extracted.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if extracted != binary:
        shutil.copy2(extracted, binary)
        binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binary


def select_mihomo_asset() -> str:
    api_url = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
    # 增加 verify=False
    data = requests.get(api_url, headers={"User-Agent": "free-node-autotest"}, timeout=SOURCE_TIMEOUT, verify=False, proxies=PROXIES).json()
    assets = data.get("assets", [])
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "darwin":
        os_token = "darwin"
    elif system == "linux":
        os_token = "linux"
    elif system == "windows":
        os_token = "windows"
    else:
        raise RuntimeError(f"unsupported OS for Mihomo download: {system}")

    if machine in {"x86_64", "amd64"}:
        arch_tokens = ["amd64-compatible", "amd64"]
    elif machine in {"arm64", "aarch64"}:
        arch_tokens = ["arm64"]
    else:
        raise RuntimeError(f"unsupported architecture for Mihomo download: {machine}")

    candidates: list[tuple[int, str]] = []
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        download_url = str(asset.get("browser_download_url", ""))
        if not download_url:
            continue
        if os_token not in name:
            continue
        if not any(token in name for token in arch_tokens):
            continue
        if not (name.endswith(".gz") or name.endswith(".zip")):
            continue
        score = 0
        if "compatible" in name:
            continue            # 直接跳过这个资产
        candidates.append((score, download_url))

    if not candidates:
        raise RuntimeError("no matching Mihomo release asset found")
    candidates.sort(reverse=True)
    return candidates[0][1]


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


def _represent_str(dumper: yaml.Dumper, data: str):
    # 含非 ASCII（旗帜等）用单引号，避免 \U 转义；其余双引号防止 953e8078 等被当成数字
    style = "'" if any(ord(ch) > 127 for ch in data) else '"'
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


QuotedDumper.add_representer(str, _represent_str)


def dump_yaml(data: Any) -> str:
    return yaml.dump(
        data,
        Dumper=QuotedDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )


def write_raw_backup(proxies: list[dict[str, Any]]) -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                "name": "AUTO-FAST",
                "type": "url-test",
                "proxies": names or ["DIRECT"],
                "url": TEST_URL,
                "interval": 120,
            }
        ],
        "rules": [
            "MATCH,AUTO-FAST",
        ],
    }
    RAW_PATH.write_text(dump_yaml(payload), encoding="utf-8")
    print(f"[INFO] raw backup written path={RAW_PATH} proxies={len(nodes)}")


def load_previous_source_proxies(source: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = str(source.get("prefix") or "")
    name = str(source.get("name") or "")
    if not HISTORY_DIR.is_dir():
        print(f"[WARN] source={name} no proxies; raw backup dir missing, skip reuse")
        return []
    pat = re.compile(r"(20\d{6})-(\d{4})")
    ranked: list[tuple[str, Path]] = []
    for path in HISTORY_DIR.glob("*raw.yaml"):
        match = pat.search(path.name)
        if match:
            ranked.append((match.group(1) + match.group(2), path))
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
                f"[INFO] source={name} reused previous raw "
                f"proxies={len(found)} file={path.name} stamp={stamp}"
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
    if not proxies:
        return []

    engine = find_or_install_mihomo()
    with tempfile.TemporaryDirectory(prefix="free-node-autotest-") as temp_name:
        temp_dir = Path(temp_name)
        config_path = temp_dir / "benchmark.yaml"
        controller_port = find_free_port()
        controller_url = f"http://127.0.0.1:{controller_port}"
        metrics = _benchmark_batch(
            engine, temp_dir, config_path, controller_url, controller_port, list(proxies)
        )
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
    return (1 / latency) * 0.6 + region_bonus(region) * 0.3 + stability * 0.1


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
    if not OUTPUT_PATH.exists():
        return []
    try:
        data = yaml.safe_load(OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("proxies"), list):
        return []
    metrics: list[ProxyMetric] = []
    for proxy in data["proxies"]:
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
    return metrics


def build_config(metrics: list[ProxyMetric]) -> dict[str, Any]:
    if not metrics:
        metrics = [build_direct_fallback_metric()]

    proxies = [item.proxy for item in metrics]
    all_names = [item.proxy["name"] for item in metrics]
    hk_names = names_for_region(metrics, "HK")
    jp_names = names_for_region(metrics, "JP")
    us_names = names_for_region(metrics, "US")
    ai_names = low_latency_pool(metrics)

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
                "name": "AUTO-FAST",
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
                "name": "AI-POOL",
                "type": "url-test",
                "proxies": ai_names,
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "FALLBACK",
                "type": "fallback",
                "proxies": ["AUTO-FAST", "HK-POOL", "JP-POOL", "US-POOL"],
                "url": TEST_URL,
                "interval": 120,
            },
            {
                "name": "PROXY",
                "type": "select",
                "proxies": ["AUTO-FAST", "FALLBACK"],
            },
        ],
        "rules": [
            "DOMAIN-SUFFIX,openai.com,AI-POOL",
            "DOMAIN-SUFFIX,chatgpt.com,AI-POOL",
            "DOMAIN-SUFFIX,claude.ai,AI-POOL",
            "DOMAIN-SUFFIX,anthropic.com,AI-POOL",
            "GEOIP,CN,DIRECT",
            "MATCH,PROXY",
        ],
    }


def write_config(config: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
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
        "DOMAIN-SUFFIX,openai.com,AI-POOL",
        "DOMAIN-SUFFIX,chatgpt.com,AI-POOL",
        "DOMAIN-SUFFIX,claude.ai,AI-POOL",
        "DOMAIN-SUFFIX,anthropic.com,AI-POOL",
        "GEOIP,CN,DIRECT",
        "MATCH,PROXY",
    ):
        if rule not in rules:
            raise RuntimeError(f"generated config missing rule: {rule}")


def print_summary(total_nodes: int, candidates: int, metrics: list[ProxyMetric]) -> None:
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
    total_nodes, candidates = collect_proxies()
    metrics: list[ProxyMetric] = []

    if candidates:
        try:
            metrics = benchmark_proxies(candidates)
        except Exception as exc:
            print(f"[WARN] real latency benchmark unavailable: {exc}")

    if not metrics:
        metrics = load_existing_metrics()
        if metrics:
            print("[WARN] no live nodes passed; reusing previous non-empty output as degraded fallback")

    if not metrics:
        metrics = [build_direct_fallback_metric()]
        print("[WARN] no live or previous nodes; using DIRECT-FALLBACK degraded config")

    order = {str(proxy["name"]): index for index, proxy in enumerate(candidates)}
    metrics.sort(key=lambda item: order.get(str(item.proxy["name"]), 10**9))
    config = build_config(metrics)
    validate_config(config)
    write_config(config)
    print_summary(total_nodes, len(candidates), metrics)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise