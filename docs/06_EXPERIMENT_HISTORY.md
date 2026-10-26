# 06 — Lịch sử thí nghiệm (tóm tắt, để Claude Code hiểu bối cảnh)

Tài liệu gốc nằm trong Project "ML stock" trên claude.ai (thư mục `output/output/`). Bảng dưới chỉ ghi các con số đã có trong tài liệu/file kết quả; **định nghĩa nhãn khác nhau giữa các TN nên không so sánh trực tiếp**.

| TN | Nội dung | Kết luận | Nguồn |
|---|---|---|---|
| TN01 | Dự báo T+1, LightGBM | GO có điều kiện. Precision top: 26,7% (loại mã sát trần 22,4%) vs base 13,5% | `Bien_ban_kiem_dinh_TN01.docx`, `data/model_scores.csv` |
| TN02 | Forward 5 phiên | NO-GO. 24,75% vs base 13,8%; LN top10 +1,48% trước phí | `data/model_scores_tn02.csv` |
| TN03 | Forward 10 phiên + ngành + TA | NO-GO. 24,3% vs base 14,5%; 2026: LN top10 −0,48% | `Motion_Doc_TN03`, `Bien_ban_kiem_dinh_TN03.docx` |
| TN04 | Capitulation 4 điều kiện | NO-GO. In-sample 55,2% co về 31,3% trên holdout 2015–2022 (winner's curse) | `Bien_ban_kiem_dinh_TN04.docx` |
| TN05 | Lõi capitulation (RSI<30 ≥3 phiên + vol ≥1,5× MA20) + regime, sau phí | GO theo tiêu chí chiết khấu → chỉ vào paper trading. R2: hit 37,2%, +2,03%/sự kiện sau phí | `Bien_ban_kiem_dinh_TN05.docx`, `TN05_tin_hieu_2026_chi_tiet.xlsx` |
| TN06 | Hệ 2 tầng: chế độ thị trường → capitulation | Đặc tả vận hành, paper trading 3 tháng từ 09/07/2026; backtest khi BẬT: hit 39,3%, +3,04%/lệnh (kỳ vọng co về 32–35%) | `Motion_Doc_Thi_nghiem_06_He_giao_dich_2_tang.docx`, `signals_log.csv` |
| **TN07** | **ML theo ledger hiện tại: y_bin ATR 5 phiên, value top 30% → LightGBM top 10** | **Chưa đủ bằng chứng.** WF-OOS: IC 0,040 [0,008; 0,067], excess −0,12% sau phí (CI chứa 0), calibration không đơn điệu; test 3 ngày | `docs/TN07_bien_ban_kiem_dinh.md`, `research/tn07/` |

**Hệ thống được triển khai trong repo này = TN07** (theo ledger project). TN06 là hệ quy tắc riêng chưa được đóng gói vào engine (xem `04_OPEN_ITEMS` #9).
