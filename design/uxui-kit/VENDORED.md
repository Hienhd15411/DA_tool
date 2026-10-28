# Bộ skill UX/UI (vendored)

Nguồn: https://github.com/plugin87/ux-ui-agent-skills · commit `def84a70` (v3.0.0) · giấy phép MIT (`LICENSE`).

Đã lấy: tokens, taste, accessibility, components, frameworks, workflows, templates, content, scripts (các gate),
rules/agents, `design-systems/library.json` + catalog, và 4 ví dụ tham chiếu (`examples/showcase`, `terminal`, `golden`, `component-states`).
Bỏ: `design-systems/library/` (39 MB đo từ website thật), ảnh/screenshot, evals, tests, mcp, bin.

26 skill nằm ở `/.claude/skills/` (đường dẫn kit đã đổi sang `design/uxui-kit/`, chạy từ thư mục gốc repo).
Hook của bộ kit (`hooks/`) được giữ để tham khảo nhưng **không bật** trong `.claude/settings.json`: hook Stop chặn kết thúc lượt
khi chưa có biên nhận đo, không phù hợp với phiên agent vận hành chạy theo lịch.

Chạy gate (Chromium + Playwright có sẵn trong môi trường cloud):
```
node design/uxui-kit/scripts/gate.mjs measure_render.mjs web/index.html
python3 design/uxui-kit/scripts/lint_hardcodes.py web
```

## Sửa đổi so với bản gốc
- Các script gate gọi `chromium.launch({ channel: 'chrome' })` nay chấp nhận `DS_CHROME_CHANNEL=bundled` để dùng Chromium
  có sẵn của Playwright (môi trường cloud không có Google Chrome). Không đặt biến này thì hành vi giữ nguyên.
- Cần `axe-core` cục bộ cho `axe_audit.mjs`: `cd design/uxui-kit && npm install --no-save axe-core@4.10.2` (thư mục `node_modules/` bị gitignore).
