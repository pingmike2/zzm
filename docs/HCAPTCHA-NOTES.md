# Zampto 续期 — hCaptcha 通道（NoneCap API 方案）

> 2026-11-13 更新：**已解决。** 放弃图像识别，改用 captcha solving API + 直接调业务接口，全流程 46 秒稳定成功。

## 一句话结论

```
SB UC 登录（拿 session）→ POST /api/server/renew/start → NoneCap 出 token → POST /api/server/renew → 200 success
```

实测返回：

```json
{"success":true,"message":"Server has been renewed successfully!",
 "renewal":"2026-11-12T17:53:36.000Z","nextRenewal":"2026-11-14T17:53:36.000Z"}
```

---

## 一、关键发现

### 1. 真正的续期端点在 JS chunk 里，不在 DOM 交互里

`/_next/static/chunks/a1e047a237fa8772.js`：

```js
fetch("/api/server/renew", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    server_id: e,
    captcha_provider: r,
    captcha_token: t,
    "cf-turnstile-response": t,
    "h-captcha-response": t
  })
})
```

所以只需：**拿到一个合法 hCaptcha token，然后 POST 这个接口**。不用点 Renew、不用点复选框、不用等 React 状态机。

### 2. 前置探针 `/api/server/renew/start`

```json
POST /api/server/renew/start  {"server_id": 9271}
→ {"allowed": true, "captchaProvider": "hcaptcha",
   "turnstileSiteKey": "0x4AAAAAAA6O-wKGAQBLqGWj",
   "hcaptchaSiteKey": "6646787e-7bfe-429a-a638-9826bbcc2500"}
```

- `allowed: false` → 冷却中（续期成功后约 24h），直接退出
- 顺带给出 sitekey，比从 iframe URL 里扒省事

### 3. NoneCap API

```
POST https://api.nonecap.com/v1/solves?wait=90
Authorization: Bearer nc_live_...
{"type":"hcaptcha","sitekey":"...","url":"https://dash.zampto.net/server?id=9271","user_agent":"..."}
→ 200 {"status":"solved","token":"P1_..."}    实测 16~38s
```

要点：

- `?wait=90` 直接阻塞等结果；返回 202 就轮询 `GET /v1/solves/{id}?wait=30`
- **不要传本地代理**：`127.0.0.1` 会被 422 拒（它从自己服务器出网，只认公网可达地址）。zampto 不校验 token 出口 IP，用它的池子即可
- 传 `user_agent`（页面 `navigator.userAgent`），部分站点要求 token 与 UA 一致
- 失败/取消/过期不扣费

### 4. token 不需要经由页面

直接在页面上下文 `fetch('/api/server/renew', ...)`（带登录 cookie），token 走请求体。注入 `textarea[name='h-captcha-response']` 是死路——React 受控组件不认 programmatic 赋值，hCaptcha widget 回调也不会触发。

---

## 二、脚本结构

`Zampto_HCap.py`（357 行）：

| 函数 | 职责 |
|---|---|
| `main()` | SB UC 启动 + 登录 + 交给 Playwright |
| `run_pw_flow()` | 进 `/server?id=N` → `renew/start` 探针 → 调 `_solve_via_nonecap` |
| `_solve_via_nonecap()` | NoneCap 出 token → 直接 POST `/api/server/renew` |

环境变量：

```bash
export NONECAP_API_KEY="nc_live_..."
export NONECAP_BASE_URL="https://api.nonecap.com/v1"   # 可选
# export NONECAP_PROXY=...    # 只在需要指定公网出口时设；本地地址会被拒
export HC_MODE="nc"           # nc=NoneCap（默认）| lib=回退本地图像库
export ZAMPTO_ACCOUNT="邮箱----密码"
export PROXY_SOCKS5="socks5://127.0.0.1:25080"
```

运行：

```bash
xvfb-run -a python Zampto_HCap.py
```

---

## 三、坑（保留记录）

### 3.1 本地图像识别方案为什么放弃

`hcaptcha_challenger` 库 + 视觉模型（`cline-free/nemotron-3.5-super-vl`）链路跑得通，但不是能用的方案：

- **hsw WASM 的 CSP 陷阱**：库把 `hsw.js` 注入主页面执行，dash.zampto.net 的 CSP 禁 `unsafe-eval`，`WebAssembly.instantiate` 直接 CompileError。必须改成注入 **hCaptcha 自己的 newassets iframe**（那个域允许 WASM），msgpack payload 才解得出。
- **选择器**：hCaptcha 挂在 shadow DOM 里，库的 XPath 全失效，CSS 选择器才穿得进去。
- **指纹**：裸 Playwright Chromium 会被直接拒题（`Please try again ⚠️`），必须 SB UC 登录后再 `connect_over_cdp` 接管。
- **双驱动互踢**：PW 接管后 SB 不能再点击，否则 chromedriver 会话被踢。
- **慢推理吃掉执行窗**：656KB 网格图单次推理 90~100s，两轮题 + 重试超过 300s 执行窗。worker 503 重试更致命。
- **坐标系其实是对的**：模型读得懂网格刻度（答案落在 `X[548-1048] Y[297-644]` 且与图像内容吻合），但对不代表赶得上时限。

**结论**：技术上可行、工程上不可靠。API 一次调用 20 秒，换掉 300 秒的赌博。

### 3.2 其他坑

- `page.evaluate` 传多参数必须打包成数组：`page.evaluate("async ([a,b]) => ...", [a, b])`，否则 `TypeError: takes from 2 to 3 positional arguments but 4 were given`
- `ZAMPTO_ACCOUNT` 用 `----` 分隔，密码里不要含 `----`
- 续期成功后 24h 内 `allowed:false`，别对着它反复重试
- 登录 Turnstile 凌晨容易连败，间隔拉到 5 分钟

---

## 四、备用通道

`HC_MODE=lib` 回退到本地 `hcaptcha_challenger`（需要 `OPENAI_*` 变量指向视觉模型）。现在用不上，留作 API 挂了的兜底。

## 五、成本

NoneCap 免费档 1300 credits，一次 solve ≤1 credit。失败不扣费。

## 六、历史记录（图像方案阶段，已废弃）

早期自研与库方案的过程记录见 git 历史。核心教训：

1. 检测优先级 hcap > turnstile > recaptcha（DOM 里关键字常同时存在）
2. 挑战面板 rect 只能从主文档 iframe 包围盒拿（challenge frame 是 OOPIF）
3. 必须先等图再截图，且裁到面板再喂模型
4. 点击用 CDP `Input.dispatchMouseEvent` 顶层派发
5. 图像算法只对「找不同」题有效

这些在 API 方案下全部不再需要。
