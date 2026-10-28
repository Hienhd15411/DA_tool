// áp giao diện đã lưu trước khi vẽ trang (file riêng vì CSP chặn script inline)
try { const t = localStorage.getItem('vnq_theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* storage bị chặn */ }
