# Zampto 续期 Turnstile 自动化踩坑实录

> 目标：GitHub Actions (UC Mode Chrome) 自动完成 dash.zampto.net 登录 → 续期弹窗 → Turnstile → 续期成功。
> 最终方案全部落在 `Zampto_Renew7.py`，本文记录排障过程中验证过的结论，避免后人重蹈。

## 1. execute_script 的语境陷阱（最高频炸点）

UC Mode 的 `sb.execute_script` 在 CI 上走 CDP `Runtime.evaluate`：
**脚本顶层出现 `return` 直接 `SyntaxError: Illegal return statement`**。

- 本地标准 Selenium 会把脚本包进 function，本地跑通 ≠ CI 跑通
- 同一脚本有时灵有时不灵（UC 语境轮换），极难归因
- **规范：所有 execute_script 一律裸 IIFE `(function(){ ... })()`**，全文件无例外
- 批量正则转换会产生 `return return` 损坏，改完必须逐处目检 + py_compile

## 2. 弹窗 Turnstile widget 在 closed shadow root 里

三层排查全部失败的证据链：

1. JS `querySelector`（含 shadow pierce 只能进 open root）→ null
2. `DOMSnapshot.captureSnapshot` → 弹窗 widget 的 iframe 不在主文档节点里
   （能看到的 challenges.cloudflare.com iframe 全是登录页残留）
3. 唯一暴露物：`cf-chl-widget-<id>_response` 隐藏 input（0x0）

**解法：CDP `DOM.getDocument({"depth": -1, "pierce": true})`** —— DOM agent 可以穿透 closed shadow root（JS 不行）。递归遍历 `children` + `shadowRoots`，按 `src` 含 `challenges.cloudflare.com` 或 `title` 含 `Widget containing` 匹配 IFRAME，拿 `backendNodeId` 后 `DOM.getBoxModel` 取视口坐标 quad，`Input.dispatchMouseEvent` 直点。

## 3. Turnstile iframe 的 src 属性不可信

widget iframe 导航后 **src 属性停留在 `about:blank` 或空串**，不再显示
`challenges.cloudflare.com`。按 src 匹配会扑空，按 `title="Widget containing
a Cloudflare security challenge"` 匹配才稳。

## 4. 坐标系三坑

| 坑 | 现象 | 解法 |
|---|---|---|
| 文档坐标 ≠ 视口坐标 | DOMSnapshot bounds 是文档系，页面滚动后点击落偏 | 减 `scrollX/scrollY`；或直接用 `getBoundingClientRect`（天然视口系） |
| `Input.dispatchMouseEvent` 只收视口坐标 | 文档坐标直喂 = 点到别处 | 转换后再派发 |
| 贴底残留 iframe | 登录页残留 widget 在视口底部（300x65 与弹窗 widget 同尺寸，面积并列最大），「取最大面积」会选中它 | 按 `top > vh*0.8 && bottom > vh-120` 判定残留，点击前直接 `remove()` 其 `[data-sitekey]` 容器 |

## 5. 残留清理的教训（误删弹窗 widget 两次）

- Turnstile 的 `cf-turnstile-response` input **天生 0x0**，绝不能作为「不可见」依据按 `closest('div')` 连根拔
- 按容器 id 白名单「保留」也会误删（弹窗 widget 不带登录页那套 id）
- 最终：清理只按**位置**（贴视口底边）判定残留，且只删 `[data-sitekey]` 容器节点

## 6. 出口 IP 验证的误导源

裸 `requests.get(ipify)` 显示 runner IP（Azure 20.x），让人误以为浏览器没走代理。
**必须两级验证**：requests 带 `proxies` + 浏览器级 `sb.open("https://api.ipify.org?format=json")` 读回显。两者都显示 socks5 出口 IP 才算代理生效。

## 7. reCAPTCHA vs Turnstile 判定

- 检测以 `page_source` 字符串判定为唯一裁决（JS 扫描被 shadow DOM 挡，源码文本不会）
- 页面同时加载 reCAPTCHA api.js（`api2/aframe` 分析 iframe）和 Turnstile——`[data-sitekey]` 不能作 reCAPTCHA 依据（Turnstile 容器同样带），须 `.g-recaptcha` 容器 + `recaptcha/api.js` 同时在场
- kind=turnstile 绝不进 reCAPTCHA 语音通道

## 8. 本地调试环境

UC Chrome 不支持带认证的 socks5 → 用 Xray 起本地无认证转发
（inbound `127.0.0.1:25080` → outbound socks5 上游带认证），浏览器指向本地端口。

## 最终时序（CI 成功轮）

```
登录 Turnstile (uc_gui, 1/3) → 进入服务器页 → 点 Renew Server
→ 弹窗识别 turnstile → 删贴底残留容器
→ uc_gui 坐标点击(第1次,未过) → DOM pierce 定位 (x+30, y+h/2)
→ CDP 派发点击 → checkbox 勾选 → 弹窗关闭 → 续期成功
```
