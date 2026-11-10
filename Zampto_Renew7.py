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
    if not digits:
        # 兜底：识别结果里的裸数字
        digits = "".join(ch for ch in raw if ch.isdigit())

    print(f"  [INFO] 识别原文: {raw!r} → 数字: {digits or '<空>'}")
    return digits

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

def solve_recaptcha_audio(sb, idx: int, max_attempts: int = 3) -> bool:
    """
    reCAPTCHA 语音挑战全流程：
    bframe → 切语音 → 下载 mp3 → Vosk 离线识别 → 回填验证。
    """
    print("  [INFO] 检测到 reCAPTCHA，走语音识别通道")

    if verify_recaptcha_token(sb):
        print("  [INFO] reCAPTCHA token 已存在，无需处理")
        return True

    # 1. 唤起挑战面板
    frames = get_recaptcha_frames(sb)
    if not frames.get("bframe"):
        click_recaptcha_anchor(sb)
        time.sleep(3)

    # 面板可能已打开但没有题目内容，先确认 bframe 内有挑战元素
    if not is_recaptcha_challenge_ready(sb):
        click_recaptcha_anchor(sb)
        time.sleep(3)

    for attempt in range(1, max_attempts + 1):
        print(f"  [INFO] reCAPTCHA 语音尝试 {attempt}/{max_attempts}")

        if is_recaptcha_blocked(sb):
            print("  [ERROR] bframe 显示封禁提示（Try again later）")
            return False

        origin_handle = switch_to_recaptcha_bframe(sb)
        if not origin_handle:
            return False

        try:
            if not is_audio_mode(sb):
                click_recaptcha_audio_button(sb)
                time.sleep(random.uniform(2, 4))
                if not is_audio_mode(sb):
                    print("  [WARN] 未进入语音模式，重试点击")
                    click_recaptcha_audio_button(sb)
                    time.sleep(2)

            audio_url = get_recaptcha_audio_url(sb, timeout=25)
            if audio_url == "__BLOCKED__":
                exit_recaptcha_bframe(sb, origin_handle)
                print("  [ERROR] 出口 IP 被 Google 判定为自动化，语音通道不可用")
                return False
            if not audio_url:
                print("  [WARN] 未取到音频链接")
                exit_recaptcha_bframe(sb, origin_handle)
                time.sleep(2)
                continue

            print(f"  [INFO] 音频链接 {(audio_url[:60])}...")
            path = download_recaptcha_audio(sb, audio_url)
            exit_recaptcha_bframe(sb, origin_handle)
            if not path:
                continue

            answer = transcribe_recaptcha_audio(path)
            if not answer:
                print("  [WARN] 识别为空，重新取音频")
                continue

            # 重新进入 bframe 回填
            origin_handle = switch_to_recaptcha_bframe(sb)
            if not origin_handle:
                return False
            ok = fill_recaptcha_answer(sb, answer)
            exit_recaptcha_bframe(sb, origin_handle)
            if not ok:
                print("  [WARN] 回填答案失败")
                continue

            print(f"  [INFO] 已提交答案 {answer}")
            time.sleep(4)

            if verify_recaptcha_token(sb):
                print("  [INFO] reCAPTCHA 验证通过")
                return True

            # 未通过时点一下刷新换题
            origin_handle = switch_to_recaptcha_bframe(sb)
            if origin_handle:
                try:
                    sb.execute_script('''
                        (function() {
                            var b = document.getElementById("recaptcha-reload-button");
                            if (b) b.click();
                        })()
                    ''')
                except Exception:
                    pass
                exit_recaptcha_bframe(sb, origin_handle)
            time.sleep(3)

        except Exception as e:
            exit_recaptcha_bframe(sb, origin_handle)
            print(f"  [WARN] 语音流程异常: {e}")
            time.sleep(2)

    print("  [WARN] reCAPTCHA 语音验证未通过")
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

def handle_turnstile(sb, idx: int, sid_f: str) -> bool:
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
    if "challenges.cloudflare.com" in src or "cf-turnstile" in src:
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
        if "challenges.cloudflare.com" in src or "cf-turnstile" in src:
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
                        if (r.top + r.height > vh - 10 && r.top > vh / 2) {
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
                # 首选: 轻 DOM 容器 rect(视口坐标,最准);收集全部候选并打印
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

    handle_turnstile(sb, idx, sid_f)
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
