#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, time, platform, requests, re, signal, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from seleniumbase import SB

AUTH_URL = "https://dash.zampto.net/auth/login"
DASHBOARD_URL = "https://dash.zampto.net/homepage"
OVERVIEW_URL = "https://dash.zampto.net/overview"
SERVER_URL = "https://dash.zampto.net/server?id={}"
SERVERS_URL = "https://dash.zampto.net/servers"
OUTPUT_DIR = Path("output/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CN_TZ = timezone(timedelta(hours=8))

class ClickTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise ClickTimeout()

def cn_now() -> datetime:
    return datetime.now(CN_TZ)

def calc_expiry_time(renewal_time_str: str, minutes: int = 2880) -> str:
    if not renewal_time_str:
        return "未知"

    renewal_time_str = renewal_time_str.strip()

    formats = [
        "%b %d, %Y at %I:%M %p UTC",
        "%b %d, %Y, %I:%M %p UTC",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(renewal_time_str, fmt)
            expiry = dt.replace(
                tzinfo=timezone.utc
            ) + timedelta(minutes=minutes)

            return expiry.astimezone(CN_TZ).strftime(
                "%Y年%m月%d日 %H时%M分"
            )
        except:
            pass

    return "未知"

def parse_renewal_datetime(time_str: str) -> Optional[datetime]:
    if not time_str:
        return None

    time_str = (
        time_str
        .replace("\xa0", " ")
        .strip()
    )

    formats = [
        "%b %d, %Y at %I:%M %p UTC",
        "%b %d, %Y, %I:%M %p UTC",
        "%b %d, %Y at %I:%M %p",
        "%b %d, %Y, %I:%M %p",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except:
            pass

    return None

def mask(s: str, show: int = 1) -> str:
    if not s: return "***"
    return s[:show] + "***" if len(s) > show else s[0] + "***"

def mask_id(sid: str) -> str:
    return str(sid)[0] + "***" if sid else "****"

def safe_sid_for_filename(sid: str) -> str:
    s = str(sid)
    if len(s) <= 3:
        return s
    return f"{s[0]}x{s[-2:]}"

def is_linux():
    return platform.system().lower() == "linux"

def setup_display():
    if is_linux() and not os.environ.get("DISPLAY"):
        try:
            from pyvirtualdisplay import Display
            d = Display(visible=False, size=(1920, 1080))
            d.start()
            os.environ["DISPLAY"] = d.new_display_var
            print("[INFO] 虚拟显示已启动")
            return d
        except Exception as e:
            print(f"[ERROR] 虚拟显示失败: {e}")
            sys.exit(1)
    return None

def shot(idx: int, name: str) -> str:
    return str(OUTPUT_DIR / f"acc{idx}-{cn_now().strftime('%H%M%S')}-{name}.png")

def safe_screenshot(sb, path: str):
    try:
        sb.save_screenshot(path)
        print(f"  [INFO] 截图 → {Path(path).name}")
    except Exception as e:
        print(f"  [WARN] 截图失败: {e}")

def notify(ok: bool, username: str, server_id: str, expiry_info: str, img: str = None):
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not token or not chat: return
    try:
        status = "✅ 续期成功" if ok else "❌ 续期失败"
        text = f"{status}\n\n账号：{username}\n服务器: {server_id}\n到期: {expiry_info}\n\nZampto Auto Renew"
        if img and Path(img).exists():
            with open(img, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id": chat, "caption": text}, files={"photo": f}, timeout=60)
        else:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text}, timeout=30)
        print("  [INFO] TG推送成功")
    except Exception as e:
        print(f"  [WARN] TG推送失败: {e}")

def notify_login_fail(username: str, img: str = None):
    token, chat = os.environ.get("TG_BOT_TOKEN"), os.environ.get("TG_CHAT_ID")
    if not token or not chat: return
    try:
        text = f"❌ 登录失败\n\n账号：{username}\n\nZampto Auto Renew"
        if img and Path(img).exists():
            with open(img, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id": chat, "caption": text}, files={"photo": f}, timeout=60)
        else:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text}, timeout=30)
    except: pass

def parse_accounts(s: str) -> List[Tuple[str, str]]:
    return [(p[0].strip(), p[1].strip()) for line in s.strip().split('\n')
            if '----' in line and len(p := line.strip().split('----', 1)) == 2 and p[0].strip() and p[1].strip()]

def inject_ad_guard(sb):
    try:
        sb.execute_script('''
        (function() {
            if (window._adGuardActive) return;
            window._adGuardActive = true;

            const adSelectors = [
                'ins.adsbygoogle', 'iframe[id^="aswift"]', '#google_ads_iframe',
                'div[id^="google_ads_lib"]', 'iframe[src*="googleads"]',
                '.ad-container', '.ads-wrapper', 'div[class*="ad-box"]',
                'div[id^="ad-"]', '#bottom-anchor-container',
                'div[class*="fixed-bottom"]', '.fc-ab-root', '.ad-placement'
            ];

            const clean = () => {
                adSelectors.forEach(s => {
                    document.querySelectorAll(s).forEach(el => el.remove());
                });
                document.querySelectorAll(
                    '.modal-backdrop, div[class*="backdrop"]'
                ).forEach(el => {
                    if (el.querySelector('#turnstileContainer') ||
                        el.querySelector('#renewForm') ||
                        el.querySelector('iframe[src*="challenges.cloudflare.com"]') ||
                        (el.innerText && el.innerText.includes('Renew Server'))) {
                        return;
                    }
                    el.remove();
                });
                const modal = document.getElementById('renewModal');
                const modalVisible = modal &&
                    window.getComputedStyle(modal).display !== 'none';
                if (!modalVisible && document.body.style.overflow === 'hidden') {
                    document.body.style.setProperty('overflow', 'auto', 'important');
                }
            };

            clean();
            window._adGuardObserver = new MutationObserver(clean);
            window._adGuardObserver.observe(document.documentElement, {
                childList: true, subtree: true
            });
        })();
        ''')
    except: pass

def dismiss_cookie_only(sb) -> bool:
    try:
        result = sb.execute_script('''
            (function() {
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].textContent.trim();
                    if (text === 'Consent' || text === 'Accept' || text === 'Accept All' ||
                        text === 'Do not consent' || text === 'Reject') {
                        buttons[i].click();
                        return text;
                    }
                }
                return '';
            })()
        ''')
        if result:
            print(f"  [INFO] 已关闭Cookie弹窗 ({result})")
            time.sleep(1)
            return True
    except: pass
    return False

# Cloudflare 整页挑战处理
def is_cloudflare_interstitial(sb) -> bool:
    """
    检测是否处于 Cloudflare 整页挑战页面（非嵌入式 Turnstile）
    """
    try:
        # 排除已经显示登录表单的情况（说明是内嵌 Turnstile，不是整页挑战）
        has_login_form = sb.execute_script('''
            (function() { return !!(
                document.querySelector('input[name="identifier"]')
                || document.querySelector('input[type="email"]')
                || document.querySelector('button[type="submit"]'));
            })()
        ''')
        if has_login_form:
            return False

        # 排除已经登录成功的情况
        current_url = sb.get_current_url()
        if "dash.zampto.net" in current_url:
            return False

        # 检测 CF 整页挑战的强特征
        page_source = sb.get_page_source()
        title = sb.get_title().lower() if sb.get_title() else ""

        strong_indicators = [
            "Just a moment",
            "Verify you are human",
            "Checking your browser",
            "Checking if the site connection is secure",
        ]
        for indicator in strong_indicators:
            if indicator in page_source:
                return True

        if "just a moment" in title or "attention required" in title:
            return True

        # 页面内容极少且包含 CF 域名
        body_text_len = sb.execute_script('''
            (function() {
                return (document.body && document.body.innerText)
                    ? document.body.innerText.trim().length : 0;
            })()
        ''')
        if body_text_len < 100 and "challenges.cloudflare.com" in page_source:
            return True

        return False
    except:
        return False

def bypass_cloudflare_interstitial(sb, idx: int, max_attempts: int = 6) -> bool:
    """绕过 Cloudflare 整页挑战，多次尝试点击并通过"""
    print("  [INFO] 检测到 Cloudflare 整页挑战，尝试绕过...")
    safe_screenshot(sb, shot(idx, "cf_interstitial_start"))

    for attempt in range(max_attempts):
        print(f"  [INFO] CF 绕过尝试 {attempt + 1}/{max_attempts}")
        try:
            sb.uc_gui_click_captcha()
            time.sleep(6)
            if not is_cloudflare_interstitial(sb):
                print("  [INFO] Cloudflare 整页挑战已通过")
                return True
        except Exception as e:
            print(f"  [WARN] 尝试 {attempt + 1} 异常: {e}")
        time.sleep(3)

    # 最后尝试刷新页面
    print("  [INFO] 尝试刷新页面重新加载...")
    try:
        sb.uc_open_with_reconnect(AUTH_URL, reconnect_time=10)
        time.sleep(5)
        if not is_cloudflare_interstitial(sb):
            print("  [INFO] 刷新后 Cloudflare 挑战消失")
            return True
    except:
        pass

    print("  [ERROR] Cloudflare 整页挑战绕过失败")
    return False

RECAPTCHA_AUDIOES_URL = "https://www.google.com/recaptcha/api2/userverify"
RECAPTCHA_ANCHOR_RE = r"iframe\[src\*='recaptcha/api2/anchor'\]"
RECAPTCHA_BFRAME_RE = r"iframe\[src\*='recaptcha/api2/bframe'\]"

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_MODEL_DIR = Path("/tmp/vosk-model-small-en-us-0.15")
VOSK_MODEL_ZIP = Path("/tmp/vosk-model-small-en-us-0.15.zip")
AUDIO_DIR = Path("/tmp/recaptcha_audio")

_NUM_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "to": "2", "too": "2",
    "three": "3", "tree": "3", "four": "4", "for": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "ate": "8", "nine": "9",
    "ten": "0",
}

def is_recaptcha_present(sb) -> bool:
    """检测弹窗内是否为 reCAPTCHA（而不是 Cloudflare Turnstile）。"""
    try:
        return bool(sb.execute_script('''
            (function() {
                // 1. reCAPTCHA 的 iframe（anchor / bframe / enterprise / 旧版 challenge）
                var ifr = document.querySelectorAll(
                    "iframe[src*='recaptcha'], iframe[src*='google.com/recaptcha'], " +
                    "iframe[title*='reCAPTCHA'], iframe[title*='recaptcha']"
                );
                if (ifr.length > 0) return true;

                // 2. 显式容器
                if (document.querySelector(".g-recaptcha, #g-recaptcha")) return true;

                // 3. 隐藏 token 域（name 或 id 任一命中）
                if (document.querySelector("textarea[name='g-recaptcha-response']")) return true;
                if (document.querySelector("textarea[id^='g-recaptcha-response']")) return true;
                if (document.querySelector("[name='g-recaptcha-response']")) return true;

                // 4. script 已加载 api.js（不能只看 [data-sitekey]：
                //    Turnstile 容器同样带 data-sitekey，会误判）
                var s = document.querySelectorAll("script[src*='recaptcha/api.js']");
                if (s.length > 0 && document.querySelector(".g-recaptcha, #g-recaptcha")) return true;

                // 5. google 域名下与 reCAPTCHA 相关的子 frame（避免误判 maps/analytics/oauth）
                var all = document.querySelectorAll("iframe");
                for (var i = 0; i < all.length; i++) {
                    var src = all[i].src || "";
                    if (src.indexOf("recaptcha/api") > -1 ||
                        src.indexOf("recaptcha/enterprise") > -1 ||
                        src.indexOf("google.com/recaptcha") > -1) return true;
                }

                return false;
            })()
        '''))
    except Exception:
        return False

def detect_captcha_kind(sb) -> str:
    """返回当前验证组件类型：recaptcha / turnstile / none。"""
    try:
        kind = sb.execute_script('''
            (function() {
                function scan(root) {
                    var out = { rc: false, ts: false, googleFrame: false };
                    var frames = root.querySelectorAll ? root.querySelectorAll("iframe") : [];
                    for (var i = 0; i < frames.length; i++) {
                        var s = frames[i].src || "";
                        if (s.indexOf("recaptcha/api") > -1 ||
                            s.indexOf("recaptcha/enterprise") > -1 ||
                            s.indexOf("google.com/recaptcha") > -1) out.rc = true;
                        if (s.indexOf("turnstile") > -1 ||
                            s.indexOf("challenges.cloudflare.com") > -1) out.ts = true;
                    }
                    return out;
                }

                // 全文档扫描
                var r = scan(document);

                // 弹窗容器内再扫一遍（组件可能挂在 shadow/自定义弹窗里）
                var modalSel = [
                    "#renewModal", "[id*='renew']", "[class*='modal']",
                    "[role='dialog']", "[class*='dialog']"
                ];
                modalSel.forEach(function(sel) {
                    document.querySelectorAll(sel).forEach(function(m) {
                        var rr = scan(m);
                        if (rr.rc) r.rc = true;
                        if (rr.ts) r.ts = true;
                    });
                });

                if (r.rc) return "recaptcha";
                if (r.ts) return "turnstile";

                // 没有 iframe 时靠 DOM 特征判定
                if (document.querySelector(".g-recaptcha, #g-recaptcha")) return "recaptcha";
                if (document.querySelector("textarea[name='g-recaptcha-response']")) return "recaptcha";
                if (document.querySelector("[name='g-recaptcha-response']")) return "recaptcha";
                if (document.querySelector("input[name='cf-turnstile-response']")) return "turnstile";
                if (document.querySelector("[id*='cf-chl-widget']")) return "turnstile";
                if (document.querySelector("#turnstile-container-renew")) return "turnstile";

                // 文本兜底：reCAPTCHA 的固有文案
                var txt = document.body ? document.body.innerText : "";
                if (txt.indexOf("I'm not a robot") > -1 ||
                    txt.indexOf("reCAPTCHA") > -1 ||
                    txt.indexOf("Verification challenge") > -1) return "recaptcha";

                return "none";
            })()
        ''')
        return str(kind or "none")
    except Exception:
        return "none"

def get_recaptcha_frames(sb) -> Dict[str, str]:
    """返回 anchor / bframe 两个 iframe 的 src。"""
    try:
        return sb.execute_script('''
            (function() {
                var a = document.querySelector("iframe[src*='recaptcha/api2/anchor']");
                var b = document.querySelector("iframe[src*='recaptcha/api2/bframe']");
                return {
                    anchor: a ? a.src : "",
                    bframe: b ? b.src : "",
                    challenge: document.querySelector("textarea[name='g-recaptcha-response']")
                        ? document.querySelector("textarea[name='g-recaptcha-response']").value : ""
                };
            })()
        ''') or {}
    except:
        return {}

def switch_to_recaptcha_bframe(sb) -> Optional[str]:
    """
    给 bframe iframe 加 id，切换到该 frame，返回原始 window handle。
    之后必须调用 exit_recaptcha_bframe 还原。
    """
    try:
        ok = sb.execute_script('''
            (function() {
                var b = document.querySelector("iframe[src*='recaptcha/api2/bframe']");
                if (!b) return false;
                b.id = "__rc_bframe__";
                return true;
            })()
        ''')
        if not ok:
            print("  [WARN] 未找到 reCAPTCHA bframe")
            return None

        origin_handle = sb.driver.current_window_handle
        sb.driver.switch_to.default_content()
        sb.driver.switch_to.frame(sb.driver.find_element("css selector", "#__rc_bframe__"))
        time.sleep(0.5)
        return origin_handle
    except Exception as e:
        print(f"  [WARN] 切换到 bframe 失败: {e}")
        try:
            sb.driver.switch_to.default_content()
        except Exception:
            pass
        return None

def exit_recaptcha_bframe(sb, origin_handle: Optional[str]):
    if not origin_handle:
        return
    try:
        sb.driver.switch_to.default_content()
        sb.driver.switch_to.window(origin_handle)
    except Exception as e:
        print(f"  [WARN] 还原 frame 失败: {e}")

def click_recaptcha_audio_button(sb, wait: int = 15) -> bool:
    """在 bframe 内点击耳机图标切到语音挑战（等元素就绪）。"""
    js = '''
        (function() {
            var ids = ["recaptcha-audio-button", "audio-button"];
            for (var i = 0; i < ids.length; i++) {
                var el = document.getElementById(ids[i]);
                if (el && el.offsetParent !== null) { el.click(); return "id:" + ids[i]; }
            }
            var btns = document.querySelectorAll("button, a, div[role='button']");
            for (var j = 0; j < btns.length; j++) {
                var t = (btns[j].innerText || "").toLowerCase()
                      + (btns[j].title || "").toLowerCase()
                      + (btns[j].getAttribute("aria-label") || "").toLowerCase();
                if (t.indexOf("audio") > -1 || t.indexOf("voice") > -1) {
                    btns[j].click();
                    return "text:audio";
                }
            }
            return "";
        })()
    '''
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            r = sb.execute_script(js)
            if r:
                print(f"  [INFO] 切换到语音验证 ({r})")
                return True
        except Exception:
            pass
        time.sleep(1)

    print("  [WARN] 未找到语音切换按钮")
    return False

def get_recaptcha_audio_url(sb, timeout: int = 30) -> Optional[str]:
    """
    从 bframe 取音频直链。优先下载链接（tdownload/ndownload），再退 audio 元素。
    Host2Play 同款选择器：音频经常只在下载链接里，audio 元素可能没有 src。
    """
    deadline = time.time() + timeout
    import html as _html

    while time.time() < deadline:
        try:
            info = sb.execute_script('''
                (function() {
                    var body = document.body ? document.body.innerText : "";
                    var blocked =
                        !!document.querySelector(".rc-doscaptcha-header-text") ||
                        body.indexOf("Try again later") > -1 ||
                        body.indexOf("automated queries") > -1;

                    // 1. 下载链接（最可靠）
                    var link = document.querySelector(".rc-audiochallenge-tdownload-link")
                            || document.querySelector(".rc-audiochallenge-ndownload-link");
                    if (link) {
                        var href = link.getAttribute("href") || "";
                        if (href.length > 10) return { url: href, blocked: false };
                    }

                    // 2. audio 元素
                    var a = document.querySelector("audio#audio-source, audio source, audio");
                    if (a) {
                        var src = a.getAttribute("src") || a.src || "";
                        if (!src) {
                            var s = a.querySelector("source");
                            src = s ? (s.getAttribute("src") || s.src || "") : "";
                        }
                        if (src.length > 10) return { url: src, blocked: false };
                    }

                    return { url: "", blocked: blocked };
                })()
            ''') or {}

            if info.get("blocked"):
                print("  [WARN] Google 拒绝了音频请求（自动化判定，需换出口 IP）")
                return "__BLOCKED__"

            if info.get("url"):
                return _html.unescape(str(info["url"]))
        except Exception:
            pass
        time.sleep(1)
    return None

def is_recaptcha_blocked(sb) -> bool:
    """bframe 内是否出现封禁提示（doscaptcha / 音频错误信息）。"""
    try:
        return bool(sb.execute_script('''
            (function() {
                var h = document.querySelector(".rc-doscaptcha-header-text");
                if (h && h.textContent.toLowerCase().indexOf("try again later") > -1) return true;
                var e = document.querySelector(".rc-audiochallenge-error-message");
                if (e && e.offsetParent !== null) return true;
                return false;
            })()
        '''))
    except Exception:
        return False

def is_audio_mode(sb) -> bool:
    """bframe 是否已切到语音模式（audio-response 可见）。"""
    origin_handle = switch_to_recaptcha_bframe(sb)
    if not origin_handle:
        return False
    try:
        return bool(sb.execute_script('''
            (function() {
                var i = document.getElementById("audio-response");
                return !!(i && i.offsetParent !== null);
            })()
        '''))
    except Exception:
        return False
    finally:
        exit_recaptcha_bframe(sb, origin_handle)

def download_recaptcha_audio(sb, url: str) -> Optional[Path]:
    """
    blob: 直链用浏览器内 fetch + FileReader 转 base64 落地；
    http(s) 直链直接 requests 下载。
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIO_DIR / f"rc_{int(time.time()*1000)}.mp3"

    if url.startswith("blob:") or url.startswith("data:"):
        try:
            b64 = sb.driver.execute_async_script('''
                var src = arguments[0];
                var done = arguments[arguments.length - 1];
                fetch(src)
                    .then(function(r) { return r.arrayBuffer(); })
                    .then(function(buf) {
                        var bytes = new Uint8Array(buf);
                        var bin = "";
                        for (var i = 0; i < bytes.length; i++) {
                            bin += String.fromCharCode(bytes[i]);
                        }
                        done(btoa(bin));
                    })
                    .catch(function(e) { done(""); });
            ''', url)
            if not b64:
                print("  [WARN] blob 音频读取为空")
                return None
            import base64 as _b64
            out.write_bytes(_b64.b64decode(b64))
            print(f"  [INFO] 音频已落地 {out.name} ({out.stat().st_size} bytes)")
            return out
        except Exception as e:
            print(f"  [WARN] blob 音频落地失败: {e}")
            return None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.google.com/",
        }
        # recaptcha.net / google.com 双域互换重试（Host2Play 同款兜底）
        urls = [url]
        if "recaptcha.net" in url:
            urls.append(url.replace("recaptcha.net", "www.google.com"))
        elif "google.com" in url:
            urls.append(url.replace("www.google.com", "recaptcha.net"))

        for audio_url in urls:
            try:
                r = requests.get(audio_url, timeout=30, headers=headers)
                if r.status_code != 200 or len(r.content) < 1000:
                    continue
                out.write_bytes(r.content)
                print(f"  [INFO] 音频已下载 {out.name} ({len(r.content)} bytes)")
                return out
            except Exception as e:
                print(f"  [WARN] 下载失败 {audio_url[:60]}: {e}")
        return None
    except Exception as e:
        print(f"  [WARN] 音频下载异常: {e}")
        return None

def ensure_vosk_model() -> Optional[str]:
    """下载并解压 Vosk 小模型（约 40MB），返回模型目录。"""
    if VOSK_MODEL_DIR.exists() and (VOSK_MODEL_DIR / "am").exists():
        return str(VOSK_MODEL_DIR)

    if not VOSK_MODEL_ZIP.exists():
        print("  [INFO] 下载 Vosk 语音模型...")
        try:
            with requests.get(VOSK_MODEL_URL, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(VOSK_MODEL_ZIP, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
        except Exception as e:
            print(f"  [WARN] Vosk 模型下载失败: {e}")
            return None

    try:
        import zipfile
        with zipfile.ZipFile(VOSK_MODEL_ZIP) as z:
            z.extractall("/tmp")
        print("  [INFO] Vosk 模型解压完成")
        return str(VOSK_MODEL_DIR)
    except Exception as e:
        print(f"  [WARN] Vosk 模型解压失败: {e}")
        return None

def transcribe_recaptcha_audio(mp3_path: Path) -> str:
    """mp3 → 16k 单声道 wav → Vosk 识别 → 纯数字串。"""
    import subprocess, json as _json

    wav = mp3_path.with_suffix(".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3_path),
             "-ar", "16000", "-ac", "1", str(wav)],
            check=True, timeout=60,
        )
    except Exception as e:
        print(f"  [WARN] ffmpeg 转码失败: {e}")
        return ""

    model_dir = ensure_vosk_model()
    if not model_dir:
        return ""

    try:
        import vosk, wave
        wf = wave.open(str(wav), "rb")
        rec = vosk.KaldiRecognizer(vosk.Model(model_dir), wf.getframerate())
        rec.SetWords(True)
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)
        raw = _json.loads(rec.FinalResult()).get("text", "")
    except Exception as e:
        print(f"  [WARN] Vosk 识别失败: {e}")
        return ""

    words = [w.strip(".,!?") for w in raw.lower().split() if w.strip()]
    digits = "".join(_NUM_WORDS.get(w, "") for w in words)
    if digits:
        # 老式纯数字挑战
        answer = digits
    else:
        # 新式英文短句挑战:回填整个识别文本(Host2Play 同款)
        answer = " ".join(words)

    print(f"  [INFO] 识别原文: {raw!r} → 答案: {answer or '<空>'!r}")
    return answer

def fill_recaptcha_answer(sb, answer: str) -> bool:
    """在 bframe 里填答案并点验证（click + clear + 填入，Host2Play 同款）。"""
    js = '''
        var ans = arguments[0];
        var inp = document.getElementById("audio-response");
        if (!inp) return false;
        inp.focus();
        inp.value = "";
        inp.value = ans;
        inp.dispatchEvent(new Event("input", {bubbles: true}));
        inp.dispatchEvent(new Event("change", {bubbles: true}));
        return true;
    '''
    js_verify = '''
        (function() {
            var btn = document.getElementById("recaptcha-verify-button");
            if (btn) { btn.click(); return true; }
            return false;
        })()
    '''
    try:
        if not sb.execute_script(js, answer):
            return False
        time.sleep(random.uniform(0.5, 1.5))
        return bool(sb.execute_script(js_verify))
    except Exception as e:
        print(f"  [WARN] 填写答案异常: {e}")
        return False

def verify_recaptcha_token(sb) -> bool:
    """检查主文档 textarea 里是否拿到了 recaptcha token。"""
    try:
        return bool(sb.execute_script('''
            (function() {
                var t = document.querySelector("textarea[name='g-recaptcha-response']");
                if (t && t.value && t.value.length > 100) return true;
                var all = document.querySelectorAll("textarea[id^='g-recaptcha-response']");
                for (var i = 0; i < all.length; i++) {
                    if (all[i].value && all[i].value.length > 100) return true;
                }
                return false;
            })()
        '''))
    except:
        return False

def is_recaptcha_challenge_ready(sb) -> bool:
    """bframe 内是否已经出现挑战元素（图片题或语音面板）。"""
    origin_handle = switch_to_recaptcha_bframe(sb)
    if not origin_handle:
        return False
    try:
        return bool(sb.execute_script('''
            (function() {
                if (document.getElementById("recaptcha-audio-button")) return true;
                if (document.getElementById("audio-source")) return true;
                if (document.getElementById("recaptcha-image-button")) return true;
                if (document.querySelector(".rc-imageselect-target")) return true;
                return false;
            })()
        '''))
    except Exception:
        return False
    finally:
        exit_recaptcha_bframe(sb, origin_handle)

def click_recaptcha_anchor(sb) -> bool:
    """点击 anchor 里的『I'm not a robot』复选框，唤起挑战面板。"""
    try:
        origin_handle = sb.driver.current_window_handle
        ok = sb.execute_script('''
            (function() {
                var a = document.querySelector("iframe[src*='recaptcha/api2/anchor']");
                if (!a) return false;
                a.id = "__rc_anchor__";
                return true;
            })()
        ''')
        if not ok:
            return False

        sb.driver.switch_to.default_content()
        sb.driver.switch_to.frame(
            sb.driver.find_element("css selector", "#__rc_anchor__")
        )
        clicked = sb.execute_script('''
            (function() {
                var c = document.getElementById("recaptcha-anchor");
                if (c) { c.click(); return true; }
                var box = document.querySelector(".recaptcha-checkbox-border, #recaptcha-anchor-label");
                if (box) { box.click(); return true; }
                return false;
            })()
        ''')
        exit_recaptcha_bframe(sb, origin_handle)
        if clicked:
            print("  [INFO] 已点击 reCAPTCHA 复选框")
        return bool(clicked)
    except Exception as e:
        print(f"  [WARN] 点击复选框异常: {e}")
        try:
            sb.driver.switch_to.default_content()
        except Exception:
            pass
        return False

def _hcap_odd_icon_point(b64: str, region=None):
    """找 hCaptcha 单图挑战里那个「不一样」的图标，返回相对图片的 (x, y)。"""
    try:
        import base64 as _b64
        import io

        import numpy as np
        from PIL import Image

        im = Image.open(io.BytesIO(_b64.b64decode(b64))).convert("RGB")
        if region:
            rx, ry, rw, rh = region
            im = im.crop((int(rx), int(ry), int(rx + rw), int(ry + rh)))
        a = np.asarray(im).astype(np.float32)
        mx = a.max(axis=2)
        mn = a.min(axis=2)
        sat = (mx - mn) / np.maximum(mx, 1.0)
        val = mx / 255.0

        # 1) 先找彩色实心图标（低多边形背景是低饱和的）
        mask = (sat > 0.40) & (val > 0.10) & (val < 0.98)
        if mask.sum() < 60:
            # 2) 退路：唯一的深色实心块（灰线稿里的异类）
            mask = (val < 0.38) & (sat < 0.55)
        if mask.sum() < 60:
            return None

        ys, xs = np.nonzero(mask)
        cell = 24
        grid = {}
        for x, y in zip(xs, ys):
            k = (int(x) // cell, int(y) // cell)
            grid[k] = grid.get(k, 0) + 1
        kx, ky = max(grid.items(), key=lambda kv: kv[1])[0]
        sel = (xs // cell == kx) & (ys // cell == ky)
        return float(xs[sel].mean()), float(ys[sel].mean())
    except Exception as e:
        print(f"  [WARN] 图像定位失败: {e}")
        return None


def _ai_vision(prompt: str, images) -> str:
    """
    调 AI 视觉后端理解图像，返回文本。
    环境变量：
      AI_BASE_URL / AI_API_KEY  —— 主对端（任意 OpenAI 兼容 /v1）
      AI_VISION_MODEL           —— 主对端模型名，默认 muse-spark
      AI_FALLBACK_URL / AI_FALLBACK_KEY / AI_FALLBACK_MODEL
                                —— 备用视觉后端（主对端拒答/失败时启用）
    images 可为单张 base64 或 base64 列表（动态题多帧）。
    """
    if isinstance(images, str):
        images = [images]

    px = os.environ.get("PROXY_SOCKS5", "")
    proxies = ({"http": px.replace("socks5://", "socks5h://"),
                "https": px.replace("socks5://", "socks5h://")}
               if px else None)

    def _call(base, key, model):
        content = [{"type": "text", "text": prompt}]
        for b in images:
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b}"}})
        payload = {"model": model,
                   "messages": [{"role": "user", "content": content}],
                   "max_tokens": 3000, "temperature": 0}
        r = requests.post(f"{base.rstrip('/')}/chat/completions",
                          headers={"Authorization": f"Bearer {key}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=180, proxies=proxies)
        if r.status_code != 200:
            print(f"  [DEBUG] {model} HTTP {r.status_code}: {r.text[:100]}")
            return ""
        d = r.json()
        msg = (d.get("choices") or [{}])[0].get("message", {})
        txt = (msg.get("content") or "").strip()
        if not txt:
            # 推理型模型可能把结果留在 reasoning 里，content 为空
            txt = (msg.get("reasoning") or "").strip()
        return txt

    # 拒答特征：模型认出验证码并拒绝解
    REFUSAL = ("我不能", "不能帮", "无法帮", "不能描述", "不能提供",
               "hCaptcha", "reCAPTCHA", "验证挑战", "确认你是真人",
               "I can't", "I cannot", "I'm not able", "as an AI")

    def _is_refusal(text):
        t = text or ""
        return any(k in t for k in REFUSAL) and not text.strip().startswith("{")

    # 后端 0：cline CLI（agent 模式，模型自写脚本分析图，实测不拒答）
    if os.environ.get("AI_CLI_DIR") and os.environ.get("AI_CLI_MODEL"):
        out = _ai_vision_cli(prompt, images[0] if images else "")
        if out:
            return out
        print("  [DEBUG] cline CLI 无结果，切主对端")

    # 主对端
    base = os.environ.get("AI_BASE_URL", "")
    key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_VISION_MODEL", "muse-spark")
    if base and key:
        try:
            out = _call(base, key, model)
            if out and not _is_refusal(out):
                return out
            if out:
                print(f"  [DEBUG] 主对端拒答({model})，切备用")
            else:
                print("  [DEBUG] 主对端空返回，尝试备用")
        except Exception as e:
            print(f"  [WARN] 主对端请求失败: {e}")

    # 备用视觉后端
    fb_url = os.environ.get("AI_FALLBACK_URL", "")
    fb_key = os.environ.get("AI_FALLBACK_KEY", "")
    fb_model = os.environ.get("AI_FALLBACK_MODEL", "")
    if fb_url and fb_key and fb_model:
        try:
            out = _call(fb_url, fb_key, fb_model)
            if out:
                return out
        except Exception as e:
            print(f"  [WARN] 备用视觉后端失败: {e}")

    return ""


def _solve_hcaptcha_via_lib(sb, timeout: int = 180) -> bool:
    """
    用 hcaptcha_challenger 的 AgentV 处理当前页面的 hCaptcha。
    需要 Playwright：通过 CDP 接上 SeleniumBase 已启动的同一个浏览器。
    环境变量：OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL（见 AgentConfig）
    """
    import asyncio

    from playwright.async_api import async_playwright

    from hcaptcha_challenger import AgentConfig, AgentV
    from hcaptcha_challenger.models import ChallengeSignal

    dbg = sb.driver.capabilities["goog:chromeOptions"]["debuggerAddress"]
    print(f"  [INFO] 库驱动接管 CDP {dbg}")
    # 核对 frame URL 是否匹配库的选择器规则
    try:
        urls = sb.driver.execute_script("""
            return Array.from(document.querySelectorAll('iframe'))
                .map(function(f){ return f.src || ''; })
                .filter(function(u){ return u.indexOf('hcaptcha') >= 0; });
        """)
        print(f"  [DEBUG] hCaptcha iframe 列表: {urls}")
    except Exception as e:
        print(f"  [DEBUG] 取 iframe 失败: {e}")

    async def _run():
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(f"http://{dbg}")
            ctx = (browser.contexts[0] if browser.contexts
                   else await browser.new_context())
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            config = AgentConfig()
            print(f"  [INFO] 库 AI 后端: {config.OPENAI_BASE_URL}"
                  f" / {config.OPENAI_MODEL}")
            agent = AgentV(page=page, agent_config=config)
            sig = await asyncio.wait_for(agent.wait_for_challenge(),
                                         timeout=timeout)
            print(f"  [INFO] 库返回: {sig}")
            return sig == ChallengeSignal.SUCCESS
        finally:
            try:
                await pw.stop()
            except Exception:
                pass

    try:
        return asyncio.run(_run())
    except RuntimeError:
        # 已有事件循环（同线程）→ 新开线程跑
        import threading
        box = {}

        def _t():
            try:
                box["r"] = asyncio.run(_run())
            except Exception as e:
                box["e"] = e

        th = threading.Thread(target=_t)
        th.start()
        th.join(timeout + 30)
        if "e" in box:
            raise box["e"]
        return bool(box.get("r"))


def _ai_vision_cli(prompt: str, image_b64: str) -> str:
    """
    走 cline CLI 的视觉后端（agent 模式，模型会自己写脚本分析图片）。
    环境变量：AI_CLI_DIR（cline 仓库目录）、AI_CLI_MODEL（模型名）。
    图片落盘到临时文件，让模型读文件而不是把 base64 塞进参数。
    """
    cli_dir = os.environ.get("AI_CLI_DIR", "")
    model = os.environ.get("AI_CLI_MODEL", "")
    if not cli_dir or not model:
        return ""
    try:
        import base64 as _b64
        import subprocess as _sp
        import tempfile

        fd, img_path = tempfile.mkstemp(suffix=".png",
                                        dir="/tmp", prefix="hcap_ai_")
        with os.fdopen(fd, "wb") as fh:
            fh.write(_b64.b64decode(image_b64))

        task = (f"读取图片 {img_path}。\n{prompt}\n"
                "只输出一行 JSON，不要写分析过程，不要执行其他工具。")
        r = _sp.run(["node", "src/cli.js", "-p", "-m", model, task],
                    cwd=cli_dir, capture_output=True, text=True, timeout=240)
        out = (r.stdout or "") + (r.stderr or "")
        try:
            os.unlink(img_path)
        except Exception:
            pass
        # 取最后一段含 points 的 JSON
        import json as _json
        import re as _re
        for m in reversed(list(_re.finditer(r"\{[^{}]*\"points\"[^{}]*\}", out))):
            try:
                d = _json.loads(m.group(0))
                if d.get("points"):
                    return _json.dumps(d)
            except Exception:
                continue
        return ""
    except Exception as e:
        print(f"  [WARN] cline CLI 视觉失败: {e}")
        return ""


def _hcap_frames(page):
    """返回 hCaptcha 的 checkbox / challenge 两个 frame。"""
    ck = ch = None
    try:
        for f in page.get_frames():
            u = (f.url or "")
            if "hcaptcha.com" not in u:
                continue
            if "checkbox" in u:
                ck = f
            elif "challenge" in u:
                ch = f
    except Exception:
        pass
    return ck, ch


def _hcap_passed(page) -> bool:
    """token 在主文档的 h-captcha-response / g-recaptcha-response 里。"""
    for sel in ("[name='h-captcha-response']", "[name='g-recaptcha-response']"):
        try:
            v = page.run_js(
                f"return (document.querySelector(\"{sel}\") || {{}}).value")
            if v and len(str(v)) > 30:
                return True
        except Exception:
            pass
    try:
        for f in page.get_frames():
            if "hcaptcha.com" not in (f.url or ""):
                continue
            ok = f.run_js(
                "return !!document.querySelector('.checkmark, [aria-checked=\"true\"]')")
            if ok:
                return True
    except Exception:
        pass
    return False


JS_RENEW_START = """
var cb = arguments[arguments.length - 1];
var sid = arguments[0];
fetch('/api/server/renew/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({server_id: sid})
}).then(function (r) {
    return r.text().then(function (t) { cb(r.status + ' :: ' + t.slice(0, 300)); });
}).catch(function (e) { cb('ERR :: ' + e); });
"""

JS_RENEW_SUBMIT = """
var cb = arguments[arguments.length - 1];
var sid = arguments[0], tok = arguments[1];
fetch('/api/server/renew', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        server_id: sid,
        captcha_provider: 'hcaptcha',
        captcha_token: tok,
        'cf-turnstile-response': tok,
        'h-captcha-response': tok
    })
}).then(function (r) {
    return r.text().then(function (t) { cb(r.status + ' :: ' + t.slice(0, 400)); });
}).catch(function (e) { cb('ERR :: ' + e); });
"""




def safe_goto(sb, url: str, wait: float = 6.0, retries: int = 2) -> bool:
    """
    用 CDP Page.navigate 导航，绕开 sb.open。

    sb.open 会带上 SeleniumBase 的自动化特征，dash.zampto.net 检测到后
    直接把整个 Chrome 进程杀掉（实测 ps 里 chrome 进程数归零），
    后续所有 driver 调用都变成 ConnectionRefused。
    """
    for _ in range(retries + 1):
        try:
            sb.driver.execute_cdp_cmd("Page.navigate", {"url": url})
            time.sleep(wait)
            # 探活：能取到 location 说明会话还在
            sb.driver.execute_script("return 1;")
            return True
        except Exception as e:
            print("  [WARN] CDP 导航失败: %s: %s" % (type(e).__name__, str(e)[:80]))
            time.sleep(2)
    return False


def _renew_by_nonecap(sb, sid: str, idx: int = 0, real_sid=None) -> bool:
    """
    NoneCap 通道：第三方 captcha solving API 出 hCaptcha token，
    然后直接 POST /api/server/renew（端点取自 _next chunk a1e047a237fa8772.js）。

    完全不碰 hCaptcha widget / React 受控组件 / 图像识别：
        POST /api/server/renew/start     -> {allowed, hcaptchaSiteKey}
        NoneCap POST /v1/solves?wait=90  -> P1_ token
        POST /api/server/renew           -> success

    环境变量：
        NONECAP_API_KEY   必填，Bearer token
        NONECAP_BASE_URL  可选，默认 https://api.nonecap.com/v1
        NONECAP_PROXY     可选，公网 socks5（NoneCap 从自己服务器出网，
                          本地 127.0.0.1 会被拒）
        HC_MODE           nc（默认）/ lib / off
    """
    if os.environ.get("HC_MODE", "nc") != "nc":
        print("  [INFO] HC_MODE=%s，跳过 NoneCap" % os.environ.get("HC_MODE"))
        return False
    key = os.environ.get("NONECAP_API_KEY", "").strip()
    if not key:
        print("  [INFO] NONECAP_API_KEY 未设置，跳过 NoneCap 通道")
        return False
    try:
        import httpx
    except ImportError:
        print("  [WARN] httpx 未安装，NoneCap 通道不可用")
        return False

    base = (os.environ.get("NONECAP_BASE_URL")
            or "https://api.nonecap.com/v1").rstrip("/")
    np_proxy = (os.environ.get("NONECAP_PROXY") or "").strip() or None
    hdr = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    # sid 可能是打码后的文件名（7x71），真实 id 由调用方传入
    _raw = str(real_sid if real_sid is not None else sid)
    sid_i = int(_raw) if _raw.isdigit() else 0
    if not sid_i:
        print("  [WARN] 无法确定 server_id，NoneCap 通道跳过")
        return False
    page_url = SERVER_URL.format(sid_i)

    # ---- 0. 用 CDP 导航到详情页（sb.open 会被站点识别并杀掉浏览器）----
    if not safe_goto(sb, page_url, wait=6.0):
        print("  [WARN] 详情页导航失败，NoneCap 通道跳过")
        return False

    # ---- 1. renew/start 探针：拿 allowed 与 hcaptchaSiteKey ----
    try:
        probe = sb.driver.execute_async_script(JS_RENEW_START, sid_i)
    except Exception as e:
        print("  [WARN] renew/start 探针失败: %s: %s" % (type(e).__name__, e))
        if os.environ.get("NONECAP_DEBUG") == "1":
            try:
                print("  [DEBUG] url=%s" % sb.get_current_url())
                print("  [DEBUG] has_token=%s" %
                      bool(sb.execute_script("return !!document.body")))
            except Exception as e2:
                print("  [DEBUG] 连 get_current_url 也失败: %r" % (e2,))
        return False
    print("  [INFO] renew/start: %s" % str(probe)[:220])
    if '"allowed":true' not in str(probe).replace(" ", ""):
        print("  [INFO] 站点当前不可续期（冷却/限流），NoneCap 通道跳过")
        return False

    sitekey = ""
    m = re.search(r'hcaptchaSiteKey\\?"?:\\?"?([0-9a-fA-F-]{36})', str(probe))
    if m:
        sitekey = m.group(1)
    if not sitekey:
        print("  [WARN] renew/start 未返回 hcaptchaSiteKey")
        return False
    print("  [INFO] hCaptcha sitekey: %s" % sitekey)

    # ---- 2. NoneCap 出 token ----
    try:
        ua = sb.execute_script("return navigator.userAgent;") or ""
    except Exception:
        ua = ""
    body = {"type": "hcaptcha", "sitekey": sitekey, "url": page_url}
    if ua:
        body["user_agent"] = ua
    if np_proxy:
        body["proxy"] = np_proxy
    print("  [INFO] NoneCap 提交: sitekey=%s url=%s proxy=%s"
          % (sitekey, page_url, "yes" if np_proxy else "no"))

    t0 = time.time()
    token = ""
    try:
        with httpx.Client(timeout=180) as cli:
            r = cli.post(base + "/solves", params={"wait": 90},
                         json=body, headers=hdr)
            data = r.json() if r.content else {}
            if r.status_code >= 400:
                print("  [WARN] NoneCap %s: %s" % (r.status_code, str(data)[:240]))
                if r.status_code in (401, 402):
                    return False
            solve_id = data.get("id")
            token = data.get("token") or ""
            status = data.get("status")
            print("  [INFO] NoneCap 首包: status=%s id=%s" % (status, solve_id))
            while not token and solve_id and time.time() - t0 < 240:
                time.sleep(5)
                r = cli.get(base + "/solves/" + str(solve_id),
                            params={"wait": 30}, headers=hdr)
                data = r.json() if r.content else {}
                token = data.get("token") or ""
                status = data.get("status")
                print("  [INFO] NoneCap 轮询: status=%s" % status)
                if status in ("failed", "cancelled", "expired"):
                    print("  [WARN] NoneCap 失败: %s" % str(data.get("error"))[:200])
                    return False
    except Exception as e:
        print("  [WARN] NoneCap 请求异常: %s: %s" % (type(e).__name__, e))
        return False

    if not token:
        print("  [WARN] NoneCap 超时未出 token")
        return False
    print("  [INFO] NoneCap token: %s... (%d chars, %.0fs)"
          % (token[:16], len(token), time.time() - t0))

    # ---- 3. 直接打 renew ----
    try:
        res = sb.driver.execute_async_script(JS_RENEW_SUBMIT, sid_i, token)
    except Exception as e:
        print("  [WARN] renew API 调用失败: %s: %s" % (type(e).__name__, e))
        return False

    print("  [INFO] renew API 返回: %s" % str(res)[:300])
    if '"success":true' in str(res).replace(" ", ""):
        print("  [INFO] NoneCap 通道续期成功")
        return True
    print("  [WARN] NoneCap 通道未通过")
    return False


def solve_hcaptcha(sb, idx: int, sid_f: str = "", max_rounds: int = 6, server_id=None) -> bool:
    """
    hCaptcha 通道：
      1. DP attach 同一浏览器，点 checkbox frame 里的勾选框
      2. 无挑战 → token 直接产生
      3. 出图像挑战 → 截挑战图 → AI 判出要点击的格子 → 逐格点击 → 提交
      4. 每轮结束复查 token
    """
    # 首选：NoneCap API（第三方求解 + 直接打 renew 接口，最快最稳）
    if _renew_by_nonecap(sb, sid_f, idx, real_sid=server_id):
        return True

    # 次选：hcaptcha_challenger 库（需要视觉模型，未配置则直接跳过）
    if os.environ.get("HCAP_LIB", "0") == "1" and os.environ.get("OPENAI_API_KEY"):
        try:
            if _solve_hcaptcha_via_lib(sb):
                print("  [INFO] hCaptcha 已通过（hcaptcha_challenger）")
                return True
            print("  [INFO] hcaptcha_challenger 未通过，回退旧通道")
        except Exception as e:
            print(f"  [WARN] hcaptcha_challenger 异常: {e}")

    if not (os.environ.get("AI_BASE_URL") or os.environ.get("OPENAI_API_KEY")):
        print("  [WARN] 未配置视觉模型（AI_BASE_URL / OPENAI_API_KEY），hCaptcha 无可用通道")
        return False

    print("  [INFO] 检测到 hCaptcha，走 AI 图像通道")

    try:
        from DrissionPage import ChromiumPage
    except ImportError:
        print("  [WARN] DrissionPage 未安装，hCaptcha 通道不可用")
        return False

    try:
        dbg = (sb.driver.capabilities.get("goog:chromeOptions") or {}).get(
            "debuggerAddress")
        page = ChromiumPage(addr_or_opts=dbg) if dbg else ChromiumPage()
    except Exception as e:
        print(f"  [WARN] DrissionPage attach 失败: {e}")
        return False

    import base64
    import random as _rnd

    def snap_b64():
        try:
            path = OUTPUT_DIR / f"hcap_{sid_f}_{int(time.time())}.png"
            page.get_screenshot(path=str(path))
            return base64.b64encode(path.read_bytes()).decode(), path
        except Exception as e:
            print(f"  [WARN] 挑战截图失败: {e}")
            return "", None

    # 1. 点复选框
    ck, _ = _hcap_frames(page)
    if ck:
        try:
            box = ck.ele("#checkbox", timeout=5) or ck.ele(
                ".checkbox", timeout=2)
            if box:
                page.actions.move_to(box, duration=_rnd.uniform(0.4, 0.9))
                time.sleep(_rnd.uniform(0.2, 0.5))
                try:
                    box.click()
                except Exception:
                    box.click(by_js=True)
                print("  [INFO] 已点击 hCaptcha 复选框")
                time.sleep(4)
        except Exception as e:
            print(f"  [WARN] 复选框点击失败: {e}")
    else:
        print("  [WARN] 未找到 hCaptcha checkbox frame")

    for round_i in range(1, max_rounds + 1):
        if _hcap_passed(page):
            print(f"  [INFO] hCaptcha 已通过（第 {round_i - 1} 轮后）")
            return True

        _, ch = _hcap_frames(page)
        if not ch:
            time.sleep(3)
            if _hcap_passed(page):
                print("  [INFO] hCaptcha 已通过")
                return True
            ck, _ = _hcap_frames(page)
            if ck:
                try:
                    ck.ele("#checkbox", timeout=2).click()
                except Exception:
                    pass
            continue

        # 取题目文案
        prompt = ""
        try:
            prompt = ch.run_js(
                "return (document.querySelector("
                "'.prompt-text, .challenge-prompt, h2') || {}).innerText || ''") or ""
        except Exception:
            pass
        print(f"  [INFO] hCaptcha 第 {round_i} 轮，题目: {prompt[:80]!r}")

        # 等挑战图真正渲染出来（题目先出、图后出，早截图会拍到半成品/未展开态）
        for _w in range(20):
            ready = False
            try:
                ready = bool(ch.run_js(
                    "return !!(document.querySelector("
                    "'canvas, .challenge-view img, .image-grid, "
                    ".task-image, [class*=challenge] img'));"))
            except Exception:
                pass
            if ready:
                break
            time.sleep(0.5)
        time.sleep(1.2)

        # 挑战图区域（challenge frame 内的可视框，视口坐标）
        rect = None
        try:
            rect = ch.run_js("""
                (function() {
                    // 优先找挑战图像本体，其次整个 challenge 容器
                    var cands = [
                        ".challenge-view", ".image-grid", "#challenge-stage",
                        ".challenge-container", ".task-grid", "canvas",
                        "[class*=challenge] img"
                    ];
                    for (var i = 0; i < cands.length; i++) {
                        var c = document.querySelector(cands[i]);
                        if (!c) continue;
                        var r = c.getBoundingClientRect();
                        if (r.width > 120 && r.height > 80) {
                            // 取整个挑战面板(含题库区)：向外扩到父级容器
                            var p = c.closest(".challenge-container, form, body");
                            var pr = (p || c).getBoundingClientRect();
                            return {x: pr.left, y: pr.top,
                                    w: pr.width, h: pr.height};
                        }
                    }
                    return null;
                })()
            """)
        except Exception:
            rect = None
        if not rect:
            # 兜底：从主文档按 iframe 的 DOM 位置算（challenge 面板 = challenge iframe 本身）
            try:
                rect = sb.driver.execute_script("""
                    var list = document.querySelectorAll(
                        "iframe[src*='hcaptcha'], iframe[src*='challenge']");
                    var best = null, area = 0;
                    for (var i = 0; i < list.length; i++) {
                        var r = list[i].getBoundingClientRect();
                        if (r.width < 100 || r.height < 80) continue;
                        var a = r.width * r.height;
                        if (a > area) {
                            area = a;
                            best = {x: r.left, y: r.top,
                                    w: r.width, h: r.height};
                        }
                    }
                    return best;
                """)
            except Exception:
                rect = None
            if rect:
                print(f"  [DEBUG] 用 iframe 包围盒: {rect}")
        print(f"  [DEBUG] 挑战区域: {rect}")
        if not rect:
            try:
                dbg_ifr = sb.driver.execute_script("""
                    var out = [];
                    document.querySelectorAll('iframe').forEach(function(f){
                        var r = f.getBoundingClientRect();
                        out.push([(f.src||'').slice(0,60), Math.round(r.left),
                                  Math.round(r.top), Math.round(r.width),
                                  Math.round(r.height)]);
                    });
                    return out;
                """)
                print(f"  [DEBUG] 页内 iframe 清单: {dbg_ifr}")
            except Exception as e:
                print(f"  [DEBUG] iframe 扫描失败: {e}")
            try:
                dbg_doc = ch.run_js(
                    "return document.documentElement.outerHTML.slice(0, 600)")
                print(f"  [DEBUG] challenge frame HTML: {dbg_doc}")
            except Exception as e:
                print(f"  [DEBUG] frame HTML 失败: {e}")

        # 采多帧（动态题如「移动的动物没去过的岛」需要看运动过程）
        frames = []
        n_frames = 5
        for fi in range(n_frames):
            fb, _fp = snap_b64()
            if fb and rect:
                try:
                    import base64 as _b64f
                    import io as _iof

                    from PIL import Image as _Imf
                    imf = _Imf.open(_iof.BytesIO(_b64f.b64decode(fb)))
                    pad = 12
                    box = (max(0, int(rect["x"]) - pad),
                           max(0, int(rect["y"]) - pad),
                           min(imf.size[0], int(rect["x"] + rect["w"]) + pad),
                           min(imf.size[1], int(rect["y"] + rect["h"]) + pad))
                    crop = imf.crop(box)
                    buf = _iof.BytesIO()
                    crop.save(buf, format="PNG")
                    fb = _b64f.b64encode(buf.getvalue()).decode()
                except Exception as e:
                    print(f"  [DEBUG] 裁剪失败: {e}")
            if fb:
                frames.append(fb)
            if fi < n_frames - 1:
                time.sleep(0.6)
        if not frames:
            time.sleep(3)
            continue
        print(f"  [INFO] 采集 {len(frames)} 帧")

        clicks = []

        # 路径 A：仅「找出不一样的图标」这类静态题才用色块算法（其他题一律交给 AI）
        if rect and ("different" in (prompt or "").lower()
                     or "不同" in (prompt or "")):
            point = _hcap_odd_icon_point(
                frames[-1],
                None if not rect else (rect["x"], rect["y"],
                                       rect["w"], rect["h"]))
            if point:
                px_, py_ = point
                if rect:
                    px_ += rect["x"]
                    py_ += rect["y"]
                print(f"  [INFO] 图像算法命中: ({px_:.0f},{py_:.0f})")
                clicks = [(px_, py_)]

        # 路径 B：AI 多帧理解 → 直接给像素坐标
        if not clicks:
            rinfo = "（截图已被裁剪到挑战面板范围）"
            first = frames[0]
            try:
                import base64 as _b64
                import io

                from PIL import Image
                im = Image.open(io.BytesIO(_b64.b64decode(first)))
                size_txt = f"整图尺寸 {im.size[0]}x{im.size[1]}"
            except Exception:
                size_txt = "整图尺寸未知"
            ask = (
                f"下面 {len(frames)} 张图是同一个验证挑战按时间顺序的连续帧。"
                f"{size_txt}；{rinfo}。\n"
                f"任务描述：{prompt!r}\n\n"
                "请直接输出结果，不要写分析过程。"
                "click 类给 1 个点；drag 类给 2 个点（起点、终点）。\n"
                "只输出一行 JSON：" 
                "{\"action\":\"click\",\"points\":[[x,y]]} 或 "
                "{\"action\":\"drag\",\"points\":[[x1,y1],[x2,y2]]}。"
                "坐标是图中像素位置。"
            )
            ans = _ai_vision(ask, frames)
            print(f"  [INFO] AI 回答: {ans[:260]!r}")
            import json as _json
            import re as _re
            ai_action = "click"
            _m2 = _re.search(r'"action"\s*:\s*"(\w+)"', ans)
            if _m2:
                ai_action = _m2.group(1).lower()
            if "drag" in (prompt or "").lower() or "拖" in (prompt or ""):
                ai_action = "drag"
            # 容错解析坐标：先严格 JSON，失败则正则抓所有 [x,y]
            # 只在「含 points 的 JSON 片段」里解析，避免抓到推理正文里的序号
            for _mm in _re.finditer(r"\{[^{}]*\"points\"[^{}]*\}", ans, _re.S):
                try:
                    d = _json.loads(_mm.group(0))
                    for p in d.get("points", []):
                        if (isinstance(p, (list, tuple)) and len(p) == 2
                                and all(isinstance(v, (int, float)) for v in p)):
                            clicks.append((float(p[0]), float(p[1])))
                except Exception:
                    continue
            if not clicks:
                # 兜底：只认 [x,y] 且 x,y 都是 3 位以上数字（坐标量级）
                pts = _re.findall(r"\[\s*(\d{2,4})\s*,\s*(\d{2,4})\s*\]", ans)
                for a_, b_ in pts[:4]:
                    clicks.append((float(a_), float(b_)))
                if clicks:
                    print(f"  [INFO] 正则兜底解析出 {len(clicks)} 点")
            if rect and clicks:
                ox, oy = max(0, int(rect["x"]) - 12), max(0, int(rect["y"]) - 12)
                clicks = [(x_ + ox, y_ + oy) for (x_, y_) in clicks]
                print(f"  [DEBUG] 裁剪偏移还原 +({ox},{oy})")
            if ai_action == "drag" and len(clicks) >= 2:
                _drag = (clicks[0], clicks[1])
                clicks = []
                print(f"  [INFO] 拖拽 {_drag[0]} → {_drag[1]}")
            else:
                _drag = None
            # 兜底：AI 只给了格子号
            if not clicks and rect:
                nums = [int(n) for n in _re.findall(r"\b([1-9])\b", ans)]
                if nums:
                    cols = rows = 3
                    cw, chh = rect["w"] / cols, rect["h"] / rows
                    for n in nums[:3]:
                        r_, c_ = divmod(n - 1, cols)
                        clicks.append((rect["x"] + c_ * cw + cw / 2,
                                       rect["y"] + r_ * chh + chh / 2))
                    print(f"  [INFO] 按格子号换算 {nums}")

        # 校验坐标在裁剪图尺寸范围内
        if clicks:
            try:
                import base64 as _b64v
                import io as _iov

                from PIL import Image as _Imv
                _sz = _Imv.open(_iov.BytesIO(_b64v.b64decode(frames[0]))).size
                bad = [c for c in clicks
                       if not (0 <= c[0] <= _sz[0] and 0 <= c[1] <= _sz[1])]
                if bad:
                    print(f"  [WARN] {len(bad)} 个坐标越界 {bad[:2]}，丢弃")
                    clicks = [c for c in clicks if c not in bad]
            except Exception:
                pass

        if not clicks:
            print("  [WARN] 未能定位目标,刷新挑战")
            try:
                ch.ele("#refresh-button, .refresh-button", timeout=2).click()
            except Exception:
                pass
            time.sleep(3)
            continue

        if locals().get("_drag"):
            (x1, y1), (x2, y2) = _drag
            try:
                sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                    "type": "mousePressed", "x": float(x1), "y": float(y1),
                    "button": "left", "clickCount": 1})
                steps = 12
                for s_ in range(1, steps + 1):
                    mx = x1 + (x2 - x1) * s_ / steps
                    my = y1 + (y2 - y1) * s_ / steps
                    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                        "type": "mouseMoved", "x": float(mx), "y": float(my),
                        "button": "left"})
                    time.sleep(0.03)
                sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                    "type": "mouseReleased", "x": float(x2), "y": float(y2),
                    "button": "left", "clickCount": 1})
                print("  [INFO] 拖拽完成")
            except Exception as e:
                print(f"  [WARN] 拖拽失败: {e}")
            time.sleep(2.0)

        for (x, y) in clicks:
            print(f"  [INFO] 点击 ({x:.0f},{y:.0f})")
            ok_click = False
            # 优先 CDP 顶层派发（视口坐标，跨 OOPIF 也准）
            try:
                for t_ in ("mousePressed", "mouseReleased"):
                    sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                        "type": t_, "x": float(x), "y": float(y),
                        "button": "left", "clickCount": 1})
                ok_click = True
            except Exception as e:
                print(f"  [WARN] CDP 点击失败: {e}")
            if not ok_click:
                try:
                    page.actions.move_to((int(x), int(y)),
                                         duration=_rnd.uniform(0.2, 0.4))
                    time.sleep(_rnd.uniform(0.15, 0.35))
                    page.actions.click((int(x), int(y)))
                except Exception as e:
                    print(f"  [WARN] DP 点击失败: {e}")
            time.sleep(_rnd.uniform(0.5, 0.9))

        time.sleep(2)
        try:
            v = ch.ele("#submit-button, .submit-button", timeout=3)
            if v:
                v.click()
                print("  [INFO] 已提交 hCaptcha 答案")
        except Exception as e:
            print(f"  [WARN] 提交失败: {e}")
        time.sleep(5)

        if _hcap_passed(page):
            print("  [INFO] hCaptcha 已通过（AI 通道）")
            return True

    print("  [WARN] hCaptcha 未通过")
    return False


def solve_recaptcha_audio(sb, idx: int, max_attempts: int = 3) -> bool:
    """
    reCAPTCHA 语音挑战全流程（DrissionPage 版）：
    attach 到 UC 同一浏览器 → get_frames 直取 anchor/bframe（不经
    switch_to,UC 下 chromedriver 对跨域 OOPIF 切换会崩）→ 切语音 →
    下载 mp3 → Vosk 离线识别 → 回填验证。移植自 Host2Play。
    """
    print("  [INFO] 检测到 reCAPTCHA，走语音识别通道")

    if verify_recaptcha_token(sb):
        print("  [INFO] reCAPTCHA token 已存在，无需处理")
        return True

    try:
        from DrissionPage import ChromiumPage
        from DrissionPage.errors import PageDisconnectedError
    except ImportError:
        print("  [WARN] DrissionPage 未安装，reCAPTCHA 通道不可用")
        return False

    # attach 到 UC 同一个浏览器
    try:
        dbg = (sb.driver.capabilities.get("goog:chromeOptions") or {}).get(
            "debuggerAddress")
        page = ChromiumPage(addr_or_opts=dbg) if dbg else ChromiumPage()
    except Exception as e:
        print(f"  [WARN] DrissionPage attach 失败: {e}")
        return False

    import html as _html
    import requests as _requests

    def find_frame(kind):
        try:
            for f in page.get_frames():
                u = f.url or ""
                if "recaptcha" in u and kind in u:
                    return f
        except Exception:
            pass
        return None

    def is_solved():
        # token 回填在主文档表单里,必须先查主文档(只扫 iframe 会误判未通过)
        try:
            tok = page.run_js(
                'return document.querySelector('
                '"textarea[name=\'g-recaptcha-response\']")?.value')
            if tok and len(str(tok)) > 30:
                return True
        except Exception:
            pass
        try:
            for f in page.get_frames():
                try:
                    token = f.run_js(
                        'return document.querySelector('
                        '"textarea[name=\'g-recaptcha-response\']")?.value')
                    if token and len(str(token)) > 30:
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        a = find_frame("anchor")
        if a:
            try:
                checked = a.run_js(
                    'return document.querySelector(\'#recaptcha-anchor\')'
                    '?.getAttribute(\'aria-checked\') === \'true\'')
                if checked:
                    return True
            except Exception:
                pass
        return False

    def blocked():
        b = find_frame("bframe")
        if not b:
            return False
        try:
            return bool(b.run_js('''
                const h = document.querySelector(
                    '.rc-doscaptcha-header-text');
                if (h && h.textContent.toLowerCase().includes(
                        'try again later')) return true;
                const e = document.querySelector(
                    '.rc-audiochallenge-error-message');
                if (e && e.offsetParent !== null) return true;
                return false;
            '''))
        except Exception:
            return False

    def click_checkbox():
        a = find_frame("anchor")
        if not a:
            return False
        box = a.ele("#recaptcha-anchor", timeout=3)
        if not box:
            return False
        try:
            page.actions.move_to(
                box, duration=random.uniform(0.4, 1.0))
            time.sleep(random.uniform(0.2, 0.5))
            box.click()
        except Exception:
            try:
                box.click(by_js=True)
            except Exception:
                return False
        time.sleep(3)
        return True

    def switch_audio():
        b = find_frame("bframe")
        if not b:
            return False
        if b.ele("#audio-response", timeout=1):
            return True
        btn = b.ele("#recaptcha-audio-button", timeout=3)
        if not btn:
            return False
        try:
            btn.click()
        except Exception:
            btn.click(by_js=True)
        time.sleep(random.uniform(1.5, 2.5))
        return bool(b.ele("#audio-response", timeout=2))

    def audio_url():
        b = find_frame("bframe")
        if not b:
            return None
        for _ in range(10):
            for sel in (".rc-audiochallenge-tdownload-link",
                        ".rc-audiochallenge-ndownload-link"):
                try:
                    link = b.ele(sel, timeout=1)
                    if link:
                        href = link.attr("href")
                        if href and len(href) > 10:
                            return _html.unescape(href)
                except Exception:
                    pass
            try:
                au = b.ele("#audio-source", timeout=1)
                if au:
                    src = au.attr("src")
                    if src and len(src) > 10:
                        return _html.unescape(src)
            except Exception:
                pass
            time.sleep(1)
        return None

    def reload():
        b = find_frame("bframe")
        if not b:
            return
        try:
            r = b.ele("#recaptcha-reload-button", timeout=2)
            if r:
                try:
                    r.click()
                except Exception:
                    r.click(by_js=True)
                time.sleep(3)
        except Exception:
            pass

    def fill_verify(text):
        b = find_frame("bframe")
        if not b:
            return False
        try:
            inp = b.ele("#audio-response", timeout=2)
            if not inp:
                return False
            inp.click()
            inp.clear()
            inp.input(text)
        except Exception:
            return False
        time.sleep(random.uniform(0.5, 1.5))
        try:
            v = b.ele("#recaptcha-verify-button", timeout=2)
            if v:
                try:
                    v.click()
                except Exception:
                    v.click(by_js=True)
        except Exception:
            pass
        return True

    def download(url):
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36"),
            "Referer": "https://www.google.com/",
        }
        urls = [url]
        if "recaptcha.net" in url:
            urls.append(url.replace("recaptcha.net", "www.google.com"))
        elif "google.com" in url:
            urls.append(url.replace("www.google.com", "recaptcha.net"))
        for u in urls:
            try:
                r = _requests.get(u, headers=headers, timeout=30,
                                  proxies=_proxies())
                r.raise_for_status()
                if len(r.content) < 1000:
                    continue
                p = AUDIO_DIR / f"rc_{int(time.time()*1000)}.mp3"
                AUDIO_DIR.mkdir(parents=True, exist_ok=True)
                p.write_bytes(r.content)
                return p
            except Exception:
                pass
        return None

    def _proxies():
        px = os.environ.get("PROXY_SOCKS5", "")
        if not px:
            return None
        # 本地 DNS + 该代理上游 = SSL EOF,必须 socks5h 让 DNS 走代理
        px = px.replace("socks5://", "socks5h://")
        return {"http": px, "https": px}

    # 等 anchor 出现
    deadline = time.time() + 15
    while time.time() < deadline:
        if find_frame("anchor"):
            break
        time.sleep(1)

    dl_fails = 0
    for i in range(max_attempts * 3):
        try:
            if is_solved():
                print("  [INFO] reCAPTCHA 已通过 (DP)")
                return True
            if blocked():
                print("  [ERROR] bframe 显示封禁提示 (Try again later)")
                return False

            if i == 0:
                click_checkbox()
                time.sleep(2)
                if is_solved():
                    print("  [INFO] reCAPTCHA 复选框直接通过")
                    return True

            if not switch_audio():
                time.sleep(3)
                if not switch_audio():
                    click_checkbox()
                    time.sleep(3)
                    continue
            time.sleep(random.uniform(2, 4))

            if blocked():
                print("  [ERROR] 音频模式检测到 IP 被封锁")
                return False

            url = audio_url()
            if not url:
                reload()
                continue

            print(f"  [INFO] 音频链接 {url[:60]}...")
            mp3 = download(url)
            if not mp3:
                dl_fails += 1
                if dl_fails >= 3:
                    print("  [ERROR] 音频连续下载失败")
                    return False
                reload()
                time.sleep(random.uniform(3, 6))
                continue
            dl_fails = 0

            text = transcribe_recaptcha_audio(mp3)
            try:
                mp3.unlink()
            except Exception:
                pass
            if not text:
                print("  [WARN] 识别为空，重新取音频")
                reload()
                time.sleep(3)
                continue

            print(f"  [INFO] 识别结果: [{text}]")
            fill_verify(text)
            time.sleep(5)
            if is_solved():
                print("  [INFO] reCAPTCHA 已通过（语音通道）")
                return True
            reload()
            time.sleep(random.uniform(2, 4))
        except PageDisconnectedError:
            print("  [WARN] DP 与浏览器断开")
            return False
        except Exception as e:
            print(f"  [WARN] DP reCAPTCHA 轮异常: {e}")
            time.sleep(2)

    print("  [WARN] reCAPTCHA 语音通道未通过")
    return False

def check_turnstile_like_dom(sb) -> bool:
    """弹窗里是否存在 Turnstile 风格的容器（用于 kind=none 时的兜底）。"""
    try:
        return bool(sb.execute_script('''
            (function() {
                if (document.querySelector("#turnstile-container-renew")) return true;
                if (document.querySelector("input[name='cf-turnstile-response']")) return true;
                if (document.querySelector("[id*='cf-chl-widget']")) return true;
                var txt = document.body ? document.body.innerText : "";
                if (txt.indexOf("Renew Server") > -1 &&
                    txt.indexOf("security verification") > -1) return true;
                return false;
            })()
        '''))
    except Exception:
        return False

def check_renew_modal_open(sb) -> bool:
    try:
        return bool(sb.execute_script('''
            (function() {

                // 1. 新版 Turnstile 容器
                if (document.querySelector('#turnstile-container-renew')) {
                    return true;
                }

                // 2. Turnstile iframe
                var iframes = document.querySelectorAll(
                    'iframe[src*="turnstile"], iframe[src*="challenges.cloudflare"]'
                );
                if (iframes.length > 0) return true;

                // 2b. reCAPTCHA iframe（CF 盾被替换成 RE 盾）
                var rc = document.querySelectorAll(
                    'iframe[src*="recaptcha"], .g-recaptcha, textarea[name="g-recaptcha-response"]'
                );
                if (rc.length > 0) return true;

                // 3. hidden response（新版已经直接出现 input）
                var input = document.querySelector(
                    'input[name="cf-turnstile-response"]'
                );
                if (input) return true;

                // 4. fallback：只要出现 renew 标题区域
                var txt = document.body ? document.body.innerText : "";
                if (txt.includes("Renew Server") &&
                    txt.includes("security verification")) {
                    return true;
                }

                return false;
            })()
        '''))
    except:
        return False

def check_turnstile_done(sb) -> bool:
    try:
        return bool(sb.execute_script('''
            (function() {
                var cf = document.querySelector("input[name='cf-turnstile-response']");
                return !!(cf && cf.value && cf.value.length > 20);
            })()
        '''))
    except:
        return False

def uc_click_with_timeout(sb, timeout: int = 20) -> bool:
    if not is_linux():
        try:
            sb.uc_gui_click_captcha()
            return True
        except:
            return False

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout)
    try:
        sb.uc_gui_click_captcha()
        signal.alarm(0)
        print(f"  [INFO] 坐标点击成功")
        return True
    except ClickTimeout:
        print(f"  [WARN] 点击超时 ({timeout}s)")
        return False
    except Exception as e:
        print(f"  [WARN] 点击异常: {e}")
        return False
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

def handle_social_prompt(sb, idx: int) -> bool:
    """处理登录后的社交媒体提示页面，点击 Continue 按钮跳过。"""
    try:
        current_url = sb.get_current_url()
        if "dash.zampto.net" not in current_url:
            return False

        has_continue = sb.execute_script('''
            (function() {
                var forms = document.querySelectorAll('form');
                for (var i = 0; i < forms.length; i++) {
                    var input = forms[i].querySelector(
                        'input[name="action"][value="continue_from_social_prompt"]'
                    );
                    if (input) {
                        var btn = forms[i].querySelector('button[type="submit"]');
                        if (btn) return true;
                    }
                }
                var btn = document.querySelector('button.continue-btn');
                if (btn && btn.textContent.trim() === 'Continue') return true;
                return false;
            })()
        ''')

        if not has_continue:
            return False

        print("  [INFO] 检测到社交媒体提示页面，点击 Continue...")
        safe_screenshot(sb, shot(idx, "social_prompt"))

        clicked = sb.execute_script('''
            (function() {
                var forms = document.querySelectorAll('form');
                for (var i = 0; i < forms.length; i++) {
                    var input = forms[i].querySelector(
                        'input[name="action"][value="continue_from_social_prompt"]'
                    );
                    if (input) {
                        var btn = forms[i].querySelector('button[type="submit"]');
                        if (btn) {
                            btn.click();
                            return "form_submit";
                        }
                        forms[i].submit();
                        return "form_direct";
                    }
                }
                var btn = document.querySelector('button.continue-btn');
                if (btn) {
                    btn.click();
                    return "class_click";
                }
                return "";
            })()
        ''')

        if clicked:
            print(f"  [INFO] 已点击 Continue 按钮 (方式: {clicked})")
            time.sleep(5)

            still_prompt = sb.execute_script('''
                var input = document.querySelector(
                    'input[name="action"][value="continue_from_social_prompt"]'
                );
                return !!input;
            ''')

            if not still_prompt:
                print("  [INFO] 已跳过社交媒体提示页面")
                return True
            else:
                print("  [WARN] 仍在社交媒体提示页面，尝试表单提交...")
                try:
                    sb.execute_script('''
                        var forms = document.querySelectorAll('form');
                        for (var i = 0; i < forms.length; i++) {
                            var input = forms[i].querySelector(
                                'input[name="action"][value="continue_from_social_prompt"]'
                            );
                            if (input) {
                                forms[i].submit();
                                break;
                            }
                        }
                    ''')
                    time.sleep(5)
                    print("  [INFO] 表单已提交")
                    return True
                except Exception as e:
                    print(f"  [WARN] 表单提交失败: {e}")
                    return False
        else:
            print("  [WARN] 未能点击 Continue 按钮")
            return False

    except Exception as e:
        print(f"  [WARN] 处理社交提示页面异常: {e}")
        return False

def handle_turnstile(sb, idx: int, sid_f: str, real_sid=None) -> bool:
    print("  [INFO] 等待验证组件...")
    time.sleep(2)

    dismiss_cookie_only(sb)
    safe_screenshot(sb, shot(idx, f"server_{sid_f}_after_click"))

    modal_open = check_renew_modal_open(sb)
    print(f"  [INFO] 续期弹窗: {'已打开' if modal_open else '未检测到'}")

    # ==========================================================
    # 判定验证组件类型（RE 盾 / CF 盾），并留证
    # page_source 检测最可靠：JS 扫不到 shadow DOM 里的 iframe
    # ==========================================================
    try:
        src = sb.get_page_source() or ""
    except Exception:
        src = ""
    if "hcaptcha.com" in src or "h-captcha" in src or "hcaptcha-widget-id" in src:
        kind = "hcaptcha"
    elif "challenges.cloudflare.com" in src or "cf-turnstile" in src:
        kind = "turnstile"
    elif "recaptcha" in src or "g-recaptcha" in src:
        kind = "recaptcha"
    else:
        kind = detect_captcha_kind(sb)
    print(f"  [INFO] 验证组件类型: {kind}")

    if kind == "none":
        # 组件可能还没渲染出来，等一会再判一次
        time.sleep(4)
        try:
            src = sb.get_page_source() or ""
        except Exception:
            src = ""
        if "hcaptcha.com" in src or "h-captcha" in src or "hcaptcha-widget-id" in src:
            kind = "hcaptcha"
        elif "challenges.cloudflare.com" in src or "cf-turnstile" in src:
            kind = "turnstile"
        elif "recaptcha" in src or "g-recaptcha" in src:
            kind = "recaptcha"
        else:
            kind = detect_captcha_kind(sb)
        print(f"  [INFO] 二次判定: {kind}")

    if kind == "none":
        # 落盘弹窗 HTML 与 iframe 列表，随 artifact 上传排查
        try:
            dump_path = OUTPUT_DIR / f"modal_dump_{sid_f}.html"
            dump_path.write_text(sb.get_page_source(), encoding="utf-8")
            print(f"  [DEBUG] 弹窗 HTML 已落盘 {dump_path.name}")
        except Exception as e:
            print(f"  [DEBUG] 弹窗 HTML 落盘失败: {e}")
        try:
            iframes_info = sb.execute_script('''
                (function() {
                    var o = [];
                    document.querySelectorAll("iframe").forEach(function(f) {
                        o.push({src: (f.src || "").slice(0, 120),
                                title: f.title || "", id: f.id || "",
                                w: f.offsetWidth, h: f.offsetHeight});
                    });
                    return o;
                })()
            ''') or []
            for f in iframes_info:
                print(f"  [DEBUG] iframe: src={f.get('src','')} title={f.get('title','')} {f.get('w')}x{f.get('h')}")
        except Exception as e:
            print(f"  [DEBUG] iframe 扫描失败: {e}")

    # ==========================================================
    # 分支 0：hCaptcha（H-CAP 盾）
    # 复选框 → 无障碍直接过；出图像挑战则截图交 AI 判点位点击
    # ==========================================================
    if kind == "hcaptcha":
        ok = solve_hcaptcha(sb, idx, sid_f, server_id=real_sid)
        safe_screenshot(sb, shot(idx, f"server_{sid_f}_hcaptcha"))
        if ok:
            return True
        if not check_renew_modal_open(sb):
            print("  [INFO] 弹窗已关闭，续期已提交")
            return True
        print("  [WARN] hCaptcha 通道未通过")
        return False

    # ==========================================================
    # 分支 1：reCAPTCHA（CF 盾已换成 RE 盾）
    # ==========================================================
    if kind == "recaptcha":
        ok = solve_recaptcha_audio(sb, idx, max_attempts=3)
        safe_screenshot(sb, shot(idx, f"server_{sid_f}_recaptcha"))
        if ok:
            return True
        if not check_renew_modal_open(sb):
            print("  [INFO] 弹窗已关闭，续期已提交")
            return True

        # reCAPTCHA 通道失败后，若页面同时具备 Turnstile 特征则回退
        if check_turnstile_like_dom(sb):
            print("  [INFO] reCAPTCHA 未通过，检测到 Turnstile 特征，回退点击通道")
        else:
            print("  [WARN] reCAPTCHA 语音通道未通过，且无 Turnstile 兜底")
            return False

    # ==========================================================
    # 分支 2：Cloudflare Turnstile
    # kind=none 也走点击通道：截图证实弹窗内是 Turnstile
    # （可能挂在 shadow DOM，选择器扫不到但 uc 坐标点击有效）
    # ==========================================================
    if kind == "none" and not modal_open:
        print("  [WARN] 未识别到验证组件且弹窗未打开，跳过")
        return False

    print("  [INFO] 使用 Turnstile 点击通道")
    if check_turnstile_done(sb):
        print("  [INFO] Turnstile 已完成")
        return True

    # 等 widget 真正渲染完成(Loading Cloudflare verification 转成 checkbox)
    # 最多 30s,每 3s 查一次快照里是否出现 turnstile iframe
    widget_ready = False
    for _ in range(10):
        try:
            snap = sb.driver.execute_cdp_cmd(
                "DOMSnapshot.captureSnapshot", {"computedStyles": []})
            strs = snap["strings"]
            joined = " ".join(strs)
            if "challenges.cloudflare.com" in joined:
                widget_ready = True
                print("  [INFO] Turnstile widget 已渲染")
                break
        except Exception:
            pass
        time.sleep(3)
    if not widget_ready:
        print("  [WARN] 30s 内 Turnstile widget 未渲染完成")

    # 清掉弹窗外的残留 Turnstile（登录页遗留 iframe 会让
    # uc_gui_click_captcha 点到隐藏 widget 上，坐标全空转）
    try:
        removed = sb.execute_script('''
            (function() {
                var n = 0;
                // 只处理 turnstile 的 iframe；隐藏 token input 天生 0x0,
                // 绝不能作为删除依据(会连容器一起拔掉)
                var ifr = document.querySelectorAll(
                    "iframe[src*='challenges.cloudflare.com']");
                for (var i = 0; i < ifr.length; i++) {
                    var el = ifr[i];
                    var r = el.getBoundingClientRect();
                    var visible = r.width > 10 && r.height > 10 &&
                                  r.bottom > 0 && r.top < window.innerHeight;
                    if (visible) continue;
                    var box = el.closest("div") || el;
                    box.remove();
                    n++;
                }
                return n;
            })()
        ''')
        if removed:
            print(f"  [INFO] 已清理弹窗外残留 Turnstile 节点: {removed} 个")
    except Exception as e:
        print(f"  [WARN] 清理残留 Turnstile 失败: {e}")

    print("  [INFO] 处理 Turnstile 验证...")
    cdp_clicked = False
    for attempt in range(3):
        print(f"  [INFO] 坐标计算完成 (第{attempt+1}次)")
        clicked = uc_click_with_timeout(sb, timeout=20)
        time.sleep(3)
        safe_screenshot(sb, shot(idx, f"ts_attempt_{attempt+1}"))

        if check_turnstile_done(sb):
            print(f"  [INFO] Turnstile 通过 (第{attempt+1}次)")
            return True

        if not check_renew_modal_open(sb):
            print(f"  [INFO] 弹窗已关闭，续期已提交")
            return True

        # 点击前: 删掉贴视口底边的登录残留 turnstile widget 容器,
        # 让页面只剩弹窗一个 widget,uc_gui 定位不再被干扰
        try:
            removed = sb.execute_script('''
                (function() {
                    var vh = window.innerHeight, n = 0;
                    var els = document.querySelectorAll(
                        "[data-sitekey], iframe[src*='challenges.cloudflare.com']"
                    );
                    for (var i = 0; i < els.length; i++) {
                        var el = els[i];
                        var host = (el.closest && el.closest("[data-sitekey]")) || el;
                        var r = host.getBoundingClientRect();
                        if (r.top > vh * 0.8 && r.top + r.height > vh - 120) {
                            host.remove();
                            n++;
                        }
                    }
                    return n;
                })()
            ''')
            if removed:
                print(f"  [INFO] 已删除 {removed} 个贴底残留 turnstile 容器")
        except Exception as e:
            print(f"  [WARN] 残留清理失败: {e}")

        # uc_gui 坐标未命中时,用 CDP 直点 iframe 中心
        # iframe 可能挂在 closed shadow root 里,JS 摸不到,
        # 改用 DOMSnapshot.captureSnapshot 取布局盒(无视 open/closed)
        if not cdp_clicked:
            try:
                box = None
                # 首选: CDP DOM.getDocument(pierce:true) 穿透 closed shadow root
                try:
                    root = sb.driver.execute_cdp_cmd("DOM.getDocument",
                                                     {"depth": -1, "pierce": True})
                    hits = []

                    def walk(node):
                        nn = node.get("nodeName", "")
                        if nn == "IFRAME":
                            attrs = node.get("attributes", [])
                            for k in range(0, len(attrs) - 1):
                                if attrs[k] in ("src", "title") and (
                                        "challenges.cloudflare.com" in attrs[k + 1]
                                        or "Widget containing" in attrs[k + 1]):
                                    hits.append(node.get("backendNodeId"))
                                    break
                        for ch in node.get("children", []) or []:
                            walk(ch)
                        for sc in node.get("shadowRoots", []) or []:
                            walk(sc)

                    walk(root["root"])
                    print(f"  [DEBUG] DOM pierce 命中 CF iframe: {len(hits)}")
                    for bid in hits:
                        try:
                            bm = sb.driver.execute_cdp_cmd(
                                "DOM.getBoxModel", {"backendNodeId": bid})
                            q = bm["model"]["content"]
                            xs, ys = q[0::2], q[1::2]
                            x0, x1 = min(xs), max(xs)
                            y0, y1 = min(ys), max(ys)
                            w, h = x1 - x0, y1 - y0
                            print(f"  [DEBUG] pierce iframe box=({x0:.0f},{y0:.0f}) {w:.0f}x{h:.0f}")
                            if w > 50 and h > 20:
                                box = {"x": x0 + 30, "y": y0 + h / 2,
                                       "w": w, "h": h, "tag": "pierce"}
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"  [WARN] DOM pierce 失败: {e}")
                # 次选: 轻 DOM 容器 rect(视口坐标);收集全部候选并打印
                try:
                    cands = sb.execute_script('''
                        (function() {
                            var out = [];
                            var els = document.querySelectorAll(
                                "#turnstile-container-renew, [class*='cf-turnstile'], [id*='cf-chl-widget'], [data-sitekey]"
                            );
                            for (var i = 0; i < els.length; i++) {
                                var r = els[i].getBoundingClientRect();
                                out.push({
                                    x: r.x, y: r.y, w: r.width, h: r.height,
                                    tag: (els[i].id || els[i].className || els[i].tagName).slice(0, 40)
                                });
                            }
                            return out;
                        })()
                    ''') or []
                except Exception:
                    cands = []
                if cands:
                    vh = None
                    for c in cands:
                        print(f"  [DEBUG] 容器候选: {c.get('tag','')} rect=({c['x']:.0f},{c['y']:.0f}) {c['w']:.0f}x{c['h']:.0f}")
                    if cands and isinstance(cands, list):
                        try:
                            vh = sb.execute_script('''
                                (function() { return window.innerHeight; })()
                            ''')
                        except Exception:
                            vh = None
                    for c in (cands if isinstance(cands, list) else []):
                        # 排除贴视口底边的登录残留 + 0 尺寸隐藏节点
                        if vh and c["y"] + c["h"] > vh - 10:
                            continue
                        if c["w"] <= 50 or c["h"] <= 20:
                            continue
                        box = {"x": c["x"] + 30, "y": c["y"] + c["h"] / 2,
                               "w": c["w"], "h": c["h"], "tag": "container"}
                        break
                if box is None or box.get("w", 0) <= 10:
                    # 次选: DOMSnapshot 快照扫全部 document,按 src 或 title 匹配
                    try:
                        snap = sb.driver.execute_cdp_cmd(
                            "DOMSnapshot.captureSnapshot", {"computedStyles": []})
                        strs = snap["strings"]
                        try:
                            vh_ = sb.execute_script('''
                                (function() { return window.innerHeight; })()
                            ''')
                        except Exception:
                            vh_ = None
                        best = None
                        ndocs = len(snap.get("documents", []))
                        print(f"  [DEBUG] 快照 document 数: {ndocs}")
                        for di in range(ndocs):
                            doc = snap["documents"][di]
                            nodes = doc["nodes"]
                            layout = doc["layout"]
                            nnames = [strs[i] if isinstance(i, int) and i < len(strs)
                                      else "" for i in nodes["nodeName"]]
                            for ni in range(len(nnames)):
                                if nnames[ni] != "IFRAME":
                                    continue
                                vals = [strs[j] for j in nodes["attributes"][ni]
                                        if isinstance(j, int) and j < len(strs)]
                                is_cf = 0
                                for k in range(0, len(vals) - 1):
                                    if vals[k] == "src" and "challenges.cloudflare.com" in vals[k + 1]:
                                        is_cf = max(is_cf, 2)
                                    if vals[k] == "title" and "Widget containing" in vals[k + 1]:
                                        is_cf = max(is_cf, 2)
                                    if vals[k] == "src" and vals[k + 1] in ("about:blank", ""):
                                        is_cf = max(is_cf, 1)
                                if is_cf == 0 or ni not in layout["nodeIndex"]:
                                    continue
                                b = layout["bounds"][layout["nodeIndex"].index(ni)]
                                # 排除贴视口底边的登录残留 iframe
                                if vh_ and b[1] + b[3] > vh_ - 10:
                                    continue
                                area = b[2] * b[3]
                                if area > 100:
                                    score = is_cf * 1000000 + area
                                    if best is None or score > best[0]:
                                        best = (score, b, di, is_cf)
                        if best:
                            b, di = best[1], best[2]
                            print(f"  [DEBUG] 快照候选 doc#{di} bounds={b}")
                            try:
                                sc = sb.execute_script('''
                                    (function() {
                                        return {x: window.scrollX || 0,
                                                y: window.scrollY || 0};
                                    })()
                                ''') or {}
                            except Exception:
                                sc = {}
                            box = {"x": b[0] + b[2] / 2 - sc.get("x", 0),
                                   "y": b[1] + b[3] / 2 - sc.get("y", 0),
                                   "w": b[2], "h": b[3], "tag": "snapshot"}
                    except Exception as e:
                        print(f"  [WARN] DOMSnapshot 失败: {e}")
                if box is None:
                    # 兜底: 穿透 open shadow root
                    box = sb.execute_script('''
                        (function() {
                            var found = null;
                            function pierce(root) {
                                if (found) return;
                                var els = root.querySelectorAll("*");
                                for (var i = 0; i < els.length; i++) {
                                    var el = els[i];
                                    if (el.tagName === "IFRAME" &&
                                        (el.src || "").indexOf("challenges.cloudflare.com") > -1) {
                                        found = el;
                                        return;
                                    }
                                    if (el.shadowRoot) pierce(el.shadowRoot);
                                }
                            }
                            pierce(document);
                            if (!found) return null;
                            var r = found.getBoundingClientRect();
                            return {x: r.x + r.width / 2, y: r.y + r.height / 2,
                                    w: r.width, h: r.height};
                        })()
                    ''')

                if box and box.get("w", 0) > 10:
                    x, y = box["x"], box["y"]
                    print(f"  [INFO] 点击目标({box.get('tag','?')}): ({x:.0f},{y:.0f}) {box['w']:.0f}x{box['h']:.0f}")
                    for t_ in ("mousePressed", "mouseReleased"):
                        sb.driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
                            "type": t_, "x": x, "y": y,
                            "button": "left", "clickCount": 1})
                    cdp_clicked = True
                    time.sleep(3)
                    safe_screenshot(sb, shot(idx, f"ts_cdp_{attempt+1}"))
                    if check_turnstile_done(sb):
                        print(f"  [INFO] Turnstile 通过 (CDP 点击,第{attempt+1}次)")
                        return True
                else:
                    print("  [DEBUG] 未定位到 turnstile 点击目标")
                    try:
                        snap2 = sb.driver.execute_cdp_cmd(
                            "DOMSnapshot.captureSnapshot", {"computedStyles": []})
                        s2 = snap2["strings"]; d2 = snap2["documents"][0]
                        n2 = d2["nodes"]
                        nms = [s2[i] if isinstance(i, int) and i < len(s2) else ""
                               for i in n2["nodeName"]]
                        icount = 0
                        for ni in range(len(nms)):
                            if nms[ni] == "IFRAME":
                                icount += 1
                                vals = [s2[j] for j in n2["attributes"][ni]
                                        if isinstance(j, int) and j < len(s2)]
                                src = ""
                                for k in range(0, len(vals) - 1):
                                    if vals[k] == "src":
                                        src = vals[k + 1][:100]
                                        break
                                print(f"  [DEBUG] 快照 iframe#{icount}: src={src!r} attrs={vals[:10]}")
                        print(f"  [DEBUG] 快照 iframe 总数: {icount}, document 数: {len(snap2.get('documents', []))}")
                    except Exception as e:
                        print(f"  [DEBUG] 快照诊断失败: {e}")
            except Exception as e:
                print(f"  [WARN] CDP 点击失败: {e}")

        if not clicked:
            time.sleep(5)

    print("  [INFO] 等待续期结果...")
    start = time.time()
    while time.time() - start < 30:
        if check_turnstile_done(sb):
            print(f"  [INFO] 检测到续期结果")
            return True
        if not check_renew_modal_open(sb):
            print(f"  [INFO] 弹窗已关闭")
            return True
        time.sleep(2)

    print("  [WARN] Turnstile 超时")
    return False

def scroll_and_get_renewal_info(sb) -> Tuple[str, str]:
    """
    获取：
        renewal_time = Server last renewed
        remain_time  = Expiry (Next Renewal)
    """

    try:
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
    except:
        pass

    renewal_time = ""
    remain_time = ""

    # ==========================================================
    # 1. Server last renewed（全文匹配 UTC）
    # ==========================================================
    try:
        renewal_time = sb.execute_script(r"""
            const body = document.body ? document.body.innerText : "";

            let m = body.match(
                /[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}\s+(AM|PM)\s+UTC/
            );
            if (m) return m[0];

            m = body.match(
                /[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s+(AM|PM)\s+UTC/
            );
            if (m) return m[0];

            // 最后只要包含 UTC 就返回
            m = body.match(/.{0,40}UTC/);
            if (m) return m[0].trim();

            return "";
        """) or ""
    except Exception:
        renewal_time = ""

    # ==========================================================
    # 2. Expiry（DOM 查找）
    # ==========================================================
    try:
        remain_time = sb.execute_script(r"""
            const divs = document.querySelectorAll("div");

            for (const div of divs) {

                const txt = (div.textContent || "").trim();

                if (
                    txt.includes("Expiry") ||
                    txt.includes("Next Renewal")
                ) {

                    const spans = div.querySelectorAll("span");

                    for (const s of spans) {

                        const t = (s.textContent || "").trim();

                        if (
                            /^\d+d/.test(t) ||
                            /^\d+h/.test(t) ||
                            /^\d+m/.test(t) ||
                            /\d+d.*\d+h/.test(t) ||
                            /\d+h.*\d+m/.test(t)
                        ) {
                            return t;
                        }

                    }
                }
            }

            return "";
        """) or ""
    except Exception:
        remain_time = ""

    # ==========================================================
    # 3. Page Source Regex 兜底
    # ==========================================================
    if not renewal_time or not remain_time:
        try:
            page = sb.get_page_source()

            # ---------- renewal ----------
            if not renewal_time:

                m = re.search(
                    r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4},\s+\d{1,2}:\d{2}\s+(?:AM|PM)\s+UTC)",
                    page
                )

                if not m:
                    m = re.search(
                        r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s+(?:AM|PM)\s+UTC)",
                        page
                    )

                if m:
                    renewal_time = m.group(1).strip()

            # ---------- remain ----------
            if not remain_time:

                m = re.search(
                    r"(\d+d\s+\d+h\s+\d+m)",
                    page
                )

                if not m:
                    m = re.search(
                        r"(\d+d\s+\d+h)",
                        page
                    )

                if not m:
                    m = re.search(
                        r"(\d+h\s+\d+m)",
                        page
                    )

                if not m:
                    m = re.search(
                        r"(\d+d)",
                        page
                    )

                if m:
                    remain_time = m.group(1).strip()

        except Exception as e:
            print(f"[WARN] Regex兜底失败: {e}")

    # ==========================================================
    # 4. Debug
    # ==========================================================
    print(f"[DEBUG] renewal_time_raw = {renewal_time}")
    print(f"[DEBUG] remain_time_raw = {remain_time}")

    if not renewal_time:
        renewal_time = "未知"

    if not remain_time:
        remain_time = "未知"

    return renewal_time, remain_time

def login(sb, user: str, pwd: str, idx: int) -> Tuple[bool, Optional[str]]:
    print(f"\n{'─' * 40}")
    print("  [INFO] 验证出口 IP...")

    try:
        proxy_env = os.environ.get("PROXY_SOCKS5", "")
        _px = {"http": proxy_env, "https": proxy_env} if proxy_env else None
        ip_info = requests.get(
            "https://api.ipify.org?format=json",
            proxies=_px,
            timeout=10
        ).json()
        print(f"  [INFO] requests 出口IP: {ip_info}")
    except Exception:
        pass

    # 浏览器级出口验证: UC Chrome 是否真走了代理,以此为准
    try:
        sb.open("https://api.ipify.org?format=json")
        time.sleep(2)
        browser_ip = sb.get_text("body").strip()[:200]
        print(f"  [INFO] 浏览器出口IP: {browser_ip}")
    except Exception as e:
        print(f"  [WARN] 浏览器出口IP获取失败: {e}")

    print(f"\n{'─' * 40}")
    print("  [INFO] 访问登录页...")

    last_shot = None

    for attempt in range(3):
        try:
            # ==========================================================
            # 访问登录页
            # ==========================================================
            sb.uc_open_with_reconnect(
                AUTH_URL,
                reconnect_time=10
            )
            time.sleep(4)

            # ==========================================================
            # Cloudflare 整页挑战
            # ==========================================================
            if is_cloudflare_interstitial(sb):
                print("  [INFO] 检测到 Cloudflare 整页挑战")

                if not bypass_cloudflare_interstitial(sb, idx):
                    last_shot = shot(idx, "cf_failed")
                    safe_screenshot(sb, last_shot)

                    if attempt < 2:
                        print("  [INFO] 准备重新尝试登录...")
                        continue

                    return False, last_shot

                time.sleep(3)

            # ==========================================================
            # 检查是否已经登录
            # ==========================================================
            current_url = sb.get_current_url()

            if (
                "dash.zampto.net" in current_url
                and "login" not in current_url
            ):
                print("  [INFO] 已登录")
                handle_social_prompt(sb, idx)
                return True, None

            # ==========================================================
            # 登录页截图
            # ==========================================================
            last_shot = shot(idx, f"login-{attempt}")
            safe_screenshot(sb, last_shot)

            # ==========================================================
            # 等待登录表单
            # ==========================================================
            print("  [INFO] 等待登录表单...")

            try:
                sb.wait_for_element(
                    "#email",
                    timeout=15
                )
            except Exception:
                print("  [ERROR] 未检测到登录表单")

                if attempt < 2:
                    time.sleep(5)
                    continue

                return False, last_shot

            # ==========================================================
            # 填写邮箱
            # ==========================================================
            print("  [INFO] 填写邮箱...")

            try:
                sb.click("#email")
                sb.clear("#email")
                sb.type("#email", user)
            except Exception as e:
                print(f"  [WARN] 普通方式填写邮箱失败: {e}")

            # 检查邮箱是否真的写入
            try:
                email_val = sb.get_attribute(
                    "#email",
                    "value"
                ) or ""
            except Exception:
                email_val = ""

            # ==========================================================
            # 邮箱 JS fallback
            # ==========================================================
            if not email_val:
                print("  [WARN] 邮箱未写入，使用 JS fallback...")

                try:
                    sb.execute_script("""
                        var input = document.querySelector('#email');

                        if (input) {
                            var setter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype,
                                'value'
                            ).set;

                            setter.call(input, arguments[0]);

                            input.dispatchEvent(
                                new Event('input', {
                                    bubbles: true
                                })
                            );

                            input.dispatchEvent(
                                new Event('change', {
                                    bubbles: true
                                })
                            );

                            input.dispatchEvent(
                                new Event('blur', {
                                    bubbles: true
                                })
                            );
                        }
                    """, user)
                except Exception as e:
                    print(f"  [ERROR] JS 填写邮箱失败: {e}")

            time.sleep(0.8)

            # ==========================================================
            # 最终确认邮箱
            # ==========================================================
            try:
                email_val = sb.get_attribute(
                    "#email",
                    "value"
                ) or ""
            except Exception:
                email_val = ""

            if email_val:
                print("  [INFO] 邮箱填写成功")
            else:
                print("  [ERROR] 邮箱仍为空")
                last_shot = shot(idx, "email_empty")
                safe_screenshot(sb, last_shot)

                if attempt < 2:
                    time.sleep(3)
                    continue

                return False, last_shot

            # ==========================================================
            # 填写密码
            # ==========================================================
            print("  [INFO] 填写密码...")

            try:
                sb.click("#password")
                sb.clear("#password")
                sb.type("#password", pwd)
            except Exception as e:
                print(f"  [WARN] 普通方式填写密码失败: {e}")

            # 检查密码是否真的写入
            try:
                pwd_val = sb.get_attribute(
                    "#password",
                    "value"
                ) or ""
            except Exception:
                pwd_val = ""

            # ==========================================================
            # 密码 JS fallback
            # ==========================================================
            if not pwd_val:
                print("  [WARN] 密码未写入，使用 JS fallback...")

                try:
                    sb.execute_script("""
                        var input = document.querySelector('#password');

                        if (input) {
                            var setter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype,
                                'value'
                            ).set;

                            setter.call(input, arguments[0]);

                            input.dispatchEvent(
                                new Event('input', {
                                    bubbles: true
                                })
                            );

                            input.dispatchEvent(
                                new Event('change', {
                                    bubbles: true
                                })
                            );

                            input.dispatchEvent(
                                new Event('blur', {
                                    bubbles: true
                                })
                            );
                        }
                    """, pwd)
                except Exception as e:
                    print(f"  [ERROR] JS 填写密码失败: {e}")

            time.sleep(1)

            # ==========================================================
            # 检查密码是否成功填写
            # ==========================================================
            try:
                pwd_val = sb.get_attribute(
                    "#password",
                    "value"
                ) or ""
            except Exception:
                pwd_val = ""

            if pwd_val:
                print("  [INFO] 密码填写成功")
            else:
                print("  [ERROR] 密码仍为空")
                last_shot = shot(idx, "password_empty")
                safe_screenshot(sb, last_shot)

                if attempt < 2:
                    time.sleep(3)
                    continue

                return False, last_shot

            # ==========================================================
            # 检测登录前 Turnstile
            # ==========================================================
            print("  [INFO] 检测登录前 Turnstile...")

            has_ts = sb.execute_script("""
                (function() { return !!(
                    document.querySelector(
                        "input[name='cf-turnstile-response']"
                    )
                    ||
                    document.querySelector(
                        "iframe[src*='turnstile']"
                    )
                    ||
                    document.querySelector(
                        "[id*='cf-chl-widget']"
                    )
                    ||
                    document.querySelector(
                        "iframe[src*='recaptcha']"
                    )
                    ||
                    document.querySelector(
                        "textarea[name='g-recaptcha-response']"
                    )
                ); })()
            """)

            # ==========================================================
            # 处理 Turnstile / reCAPTCHA
            # ==========================================================
            kind_is_recaptcha = False
            try:
                src = sb.get_page_source() or ""
            except Exception:
                src = ""
            if "recaptcha" in src or "g-recaptcha" in src:
                kind_is_recaptcha = True

            if has_ts or kind_is_recaptcha:
                print("  [INFO] 检测到验证组件，尝试处理...")

                turnstile_done = False

                # reCAPTCHA 优先走语音识别通道
                if kind_is_recaptcha:
                    turnstile_done = solve_recaptcha_audio(sb, idx, max_attempts=3)
                    if turnstile_done:
                        print("  [INFO] reCAPTCHA 已通过（语音通道）")

                for t_attempt in range(3 if not turnstile_done else 0):
                    print(
                        f"  [INFO] Turnstile 点击 "
                        f"({t_attempt + 1}/3)"
                    )

                    clicked = uc_click_with_timeout(
                        sb,
                        timeout=20
                    )

                    time.sleep(3)

                    done = sb.execute_script("""
                        (function() {
                            var cf = document.querySelector(
                                "input[name='cf-turnstile-response']"
                            );
                            return !!(cf && cf.value && cf.value.length > 20);
                        })()
                    """)

                    if done:
                        print("  [INFO] Turnstile 已通过")
                        turnstile_done = True
                        break

                    if not clicked:
                        print("  [WARN] Turnstile 点击未成功")
                        time.sleep(3)

                if not turnstile_done:
                    print(
                        "  [WARN] Turnstile 未检测到完成状态，"
                        "继续尝试提交"
                    )

            else:
                print("  [INFO] 未检测到登录 Turnstile")

            # ==========================================================
            # 点击登录
            # ==========================================================
            print("  [INFO] 点击登录...")

            try:
                sb.click("button[type='submit']")
                print("  [INFO] 登录按钮点击成功")

            except Exception as e:
                print(
                    f"  [WARN] Selenium 点击登录失败: {e}"
                )

                try:
                    sb.execute_script("""
                        var btn = document.querySelector(
                            "button[type='submit']"
                        );

                        if (btn) {
                            btn.click();
                        }
                    """)
                    print("  [INFO] JS 点击登录按钮成功")

                except Exception as js_e:
                    print(
                        f"  [ERROR] JS 点击登录失败: {js_e}"
                    )

                    last_shot = shot(
                        idx,
                        "login_button_failed"
                    )
                    safe_screenshot(
                        sb,
                        last_shot
                    )

                    if attempt < 2:
                        time.sleep(3)
                        continue

                    return False, last_shot

            # ==========================================================
            # 等待登录结果
            # ==========================================================
            print("  [INFO] 等待登录跳转...")

            login_success = False

            for wait_count in range(30):
                current_url = sb.get_current_url()

                if (
                    "dash.zampto.net" in current_url
                    and "login" not in current_url
                ):
                    login_success = True
                    break

                time.sleep(1)

            # ==========================================================
            # 登录成功
            # ==========================================================
            if login_success:
                print("  [INFO] 登录成功")

                handle_social_prompt(
                    sb,
                    idx
                )

                return True, None

            # ==========================================================
            # 登录失败截图
            # ==========================================================
            print("  [WARN] 登录后未发生跳转")

            last_shot = shot(
                idx,
                f"login_result_{attempt}"
            )

            safe_screenshot(
                sb,
                last_shot
            )

            # ==========================================================
            # 输出当前页面状态，方便排查
            # ==========================================================
            try:
                current_url = sb.get_current_url()
                print(
                    f"  [DEBUG] 当前 URL: {current_url}"
                )
            except Exception:
                pass

            if attempt < 2:
                print("  [INFO] 准备重新尝试登录...")
                time.sleep(4)

        except Exception as e:
            print(
                f"  [WARN] 尝试 {attempt + 1} 异常: {e}"
            )

            last_shot = shot(
                idx,
                f"login_exception_{attempt}"
            )

            safe_screenshot(
                sb,
                last_shot
            )

            if attempt < 2:
                time.sleep(4)

    print("  [ERROR] 3次登录尝试均失败")

    return False, last_shot

def logout(sb):
    try:
        sb.delete_all_cookies()
        sb.open("about:blank")
        time.sleep(1)
        print("  [INFO] 已退出登录")
    except: pass

def get_servers(sb, idx: int) -> Tuple[List[Dict[str, str]], str, Optional[str]]:
    servers, seen = [], set()

    sb.open(SERVERS_URL)
    time.sleep(5)

    handle_social_prompt(sb, idx)
    time.sleep(2)

    inject_ad_guard(sb)
    dismiss_cookie_only(sb)

    screenshot = shot(idx, "dashboard")
    safe_screenshot(sb, screenshot)

    src = sb.get_page_source()
    if "Access Blocked" in src or "VPN or Proxy" in src:
        return [], "⚠️ 访问被阻止", screenshot

    try:
        api_servers = sb.execute_async_script('''
            var done = arguments[0];
            fetch("https://dash.zampto.net/api/sidebar", {
                method: "GET",
                credentials: "include"
            })
            .then(r => r.json())
            .then(data => {
                var list = (data.serverSelector && data.serverSelector.servers) || [];
                done(list);
            })
            .catch(() => done([]));
        ''')

        if api_servers:
            for srv in api_servers:
                sid = str(srv.get("id", ""))
                name = srv.get("name", sid)
                if sid and sid not in seen:
                    seen.add(sid)
                    servers.append({"id": sid, "name": name})
            print(f"  [INFO] API 返回 {len(servers)} 个活跃服务器")

    except Exception as e:
        print(f"  [WARN] API 获取失败: {e}，回退到页面解析")

    if not servers:
        print("  [INFO] 回退到页面解析...")
        sb.open(SERVERS_URL)
        time.sleep(3)

        handle_social_prompt(sb, idx)
        time.sleep(2)

        inject_ad_guard(sb)
        dismiss_cookie_only(sb)

        for sid in re.findall(r"/server\?id=(\d+)", sb.get_page_source()):
            if sid not in seen:
                seen.add(sid)
                servers.append({"id": sid})

    if not servers:
        return [], "⚠️ 未找到服务器", screenshot

    return servers, "", screenshot

def renew(sb, sid: str, idx: int, username: str) -> Dict[str, Any]:
    result = {
        "server_id": sid, "success": False, "message": "", "screenshot": None,
        "old_expiry_cn": "", "new_expiry_cn": "", "expiry_info": "",
    }

    sid_m = mask_id(sid)
    sid_f = safe_sid_for_filename(sid)

    print(f"\n{'─'*40}")
    print(f"  [INFO] 续期: 服务器 (id={sid_m})")
    print(f"{'─'*40}")
    print(f"  [INFO] 访问: https://dash.zampto.net/server?id={sid_m}")

    sb.open(SERVER_URL.format(sid))
    time.sleep(4)

    handle_social_prompt(sb, idx)
    time.sleep(2)

    inject_ad_guard(sb)
    dismiss_cookie_only(sb)

    if "Access Blocked" in sb.get_page_source():
        result["message"] = "访问被阻止"
        result["expiry_info"] = "访问被阻止"
        notify(False, username, sid, result["expiry_info"])
        return result

    safe_screenshot(sb, shot(idx, f"server_{sid_f}_loaded"))

    old_renewal, old_remain = scroll_and_get_renewal_info(sb)
    old_expiry_cn = calc_expiry_time(old_renewal)
    old_dt = parse_renewal_datetime(old_renewal)
    result["old_expiry_cn"] = old_expiry_cn
    print(f"  [INFO] 当前剩余时间: {old_remain}")

    print("  [INFO] 查找续期按钮...")
    try:
        clicked = sb.execute_script(f'''
            (function() {{
                var links = document.querySelectorAll('a[onclick*="handleServerRenewal"]');
                for (var i = 0; i < links.length; i++) {{
                    if (links[i].getAttribute('onclick').includes('{sid}')) {{
                        links[i].click();
                        return "handleServerRenewal";
                    }}
                }}
                var btns = document.querySelectorAll('a.action-button, button, a');
                for (var i = 0; i < btns.length; i++) {{
                    var text = btns[i].textContent.trim();
                    if (text.includes('Renew') && !text.includes('Last') && !text.includes('Next')) {{
                        btns[i].click();
                        return "span:" + text;
                    }}
                }}
                return "";
            }})()
        ''')

        if not clicked:
            result["message"] = "未找到续期按钮"
            result["expiry_info"] = f"未找到按钮 | {old_expiry_cn}"
            safe_screenshot(sb, shot(idx, f"server_{sid_f}_nobtn"))
            notify(False, username, sid, result["expiry_info"])
            return result

        print(f"  [INFO] 已点击续期按钮 (方式: {clicked})")
    except Exception as e:
        result["message"] = f"点击失败: {e}"
        return result

    time.sleep(3)

    handle_turnstile(sb, idx, sid_f, real_sid=sid)
    time.sleep(5)

    safe_screenshot(sb, shot(idx, f"server_{sid_f}_result"))
    result["screenshot"] = shot(idx, f"server_{sid_f}_result")

    print("  [INFO] 刷新页面确认续期时间...")
    sb.open(SERVER_URL.format(sid))
    time.sleep(4)

    handle_social_prompt(sb, idx)
    time.sleep(2)

    inject_ad_guard(sb)
    dismiss_cookie_only(sb)

    new_renewal, new_remain = scroll_and_get_renewal_info(sb)
    new_expiry_cn = calc_expiry_time(new_renewal)
    new_dt = parse_renewal_datetime(new_renewal)
    result["new_expiry_cn"] = new_expiry_cn
    print(f"  [INFO] 续期后剩余时间: {new_remain}")

    final_shot = shot(idx, f"server_{sid_f}_final")
    safe_screenshot(sb, final_shot)
    result["screenshot"] = final_shot

    today_utc = datetime.utcnow().strftime("%b %d, %Y")
    today_utc2 = datetime.utcnow().strftime("%b %-d, %Y") if not sys.platform.startswith("win") else today_utc

    renewed = False
    if old_dt and new_dt and new_dt > old_dt:
        renewed = True
    elif new_renewal and old_renewal and new_renewal != old_renewal:
        renewed = True
    elif new_renewal:
        is_today = today_utc in new_renewal or today_utc2 in new_renewal
        was_today = old_renewal and (today_utc in old_renewal or today_utc2 in old_renewal)
        if is_today and not was_today:
            renewed = True

    if renewed:
        result["success"] = True
        result["expiry_info"] = f"{old_expiry_cn} -> {new_expiry_cn}"
        result["message"] = "续期成功"
    else:
        result["success"] = False
        result["expiry_info"] = f"{old_expiry_cn} (未更新)"
        result["message"] = "续期失败：时间未变化" if old_renewal == new_renewal else "续期失败：无法确认"

    notify(result["success"], username, sid, result["expiry_info"], final_shot)
    print(f"  {'[INFO]' if result['success'] else '[ERROR]'} {result['message']}")
    return result

def process(sb, user: str, pwd: str, idx: int) -> Dict[str, Any]:
    result = {"username": user, "success": False, "message": "", "servers": []}

    login_ok, login_shot = login(sb, user, pwd, idx)
    if not login_ok:
        result["message"] = "登录失败"
        notify_login_fail(user, login_shot)
        return result

    servers, error, dash_shot = get_servers(sb, idx)
    if error:
        result["message"] = error
        notify_login_fail(user, dash_shot)
        logout(sb)
        return result

    print(f"\n  [INFO] 找到 {len(servers)} 个活跃服务器")
    for s in servers:
        print(f"    - ID: {mask_id(s['id'])}")

    for srv in servers:
        r = renew(sb, srv["id"], idx, user)
        result["servers"].append(r)
        time.sleep(3)

    ok = sum(1 for s in result["servers"] if s.get("success"))
    result["success"] = ok > 0
    result["message"] = f"{ok}/{len(result['servers'])} 成功"

    logout(sb)
    return result

def main():
    acc_str = os.environ.get("ZAMPTO_ACCOUNT", "")
    if not acc_str:
        print("[ERROR] 缺少 ZAMPTO_ACCOUNT"); sys.exit(1)

    accounts = parse_accounts(acc_str)
    if not accounts:
        print("[ERROR] 无有效账号"); sys.exit(1)

    print("=" * 40)
    print("  Zampto Auto Renew")
    print("=" * 40)

    proxy = os.environ.get("PROXY_SOCKS5", "")
    if proxy:
        try:
            requests.get("https://api.ipify.org", proxies={"http": proxy, "https": proxy}, timeout=10)
            print("[INFO] 代理连接正常")
        except Exception as e:
            print(f"[WARN] 代理测试失败: {e}")

    display = setup_display()
    results = []

    try:
        try:
            import nest_asyncio
            nest_asyncio.apply()
            print("[INFO] nest_asyncio 已应用")
        except ImportError:
            pass

        opts = {"uc": True, "test": True, "locale": "en", "headed": not is_linux()}
        if proxy:
            opts["proxy"] = proxy
            print("[INFO] 使用代理")

        with SB(**opts) as sb:
            for i, (u, p) in enumerate(accounts, 1):
                r = process(sb, u, p, i)
                results.append(r)

    except Exception as e:
        print(f"[ERROR] 脚本异常: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        if display:
            display.stop()

    ok_acc = sum(1 for r in results if r.get("success"))
    total_srv = sum(len(r.get("servers", [])) for r in results)
    ok_srv = sum(sum(1 for s in r.get("servers", []) if s.get("success")) for r in results)

    print(f"\n{'='*40}")
    print(f"[INFO] 账号: {ok_acc}/{len(results)} | 服务器: {ok_srv}/{total_srv}")
    for r in results:
        status = "[INFO]" if r.get("success") else "[ERROR]"
        print(f"{status} {mask(r['username'])}: {r.get('message', '')}")
        for s in r.get("servers", []):
            s_status = "[INFO]" if s.get("success") else "[ERROR]"
            print(f"  {s_status} {mask_id(s['server_id'])}: {s.get('message', '')}")
    print(f"{'='*40}")

    sys.exit(0 if ok_srv > 0 else 1)

if __name__ == "__main__":
    main()
