# TODO — Miyano VN Accounting: Live Operation on ERPNext Core (Phase 13+)

Prior phases (Tasks 1–32) shipped: TT99 foundation + statutory reports + go-live
tooling/runbook; 34 VN tests green. This phase (see `SPEC.md`, `tasks/plan.md`):
early cutover on erpnext-only, HĐĐT, sổ sách/chứng từ in, kết chuyển 911, tax
export, GĐ2 remainder. `mvl_accounting` is parked (reference-only).

## Phase 13 — Mid-year cutover support (WS-A)
- [x] Task 33 — `as_of` mid-year mode: opening tooling + validator (BS-only, P&L rejected, 4212)
- [x] Task 34 — Runbook addendum: cutover giữa năm (docs)

## Phase 14 — Chứng từ in & sổ sách (WS-C1)
- [x] Task 35 — Print formats Phiếu thu 01-TT + Phiếu chi 02-TT (Payment Entry, số-thành-chữ)
- [x] Task 36 — Print formats Phiếu nhập kho 01-VT + Phiếu xuất kho 02-VT
- [x] Task 37 — Report Sổ quỹ tiền mặt (S07-DN, 111*)
- [x] Task 38 — Report Sổ tiền gửi ngân hàng (S08-DN, 112*)
- [x] Task 39 — Report Sổ chi tiết công nợ theo đối tượng (131/331)

### Checkpoint A — regression + pre-commit green; day-1 paper needs covered

## Phase 15 — Hóa đơn điện tử (WS-B)
- [x] Task 40 — E-invoice settings + custom fields (Company + Sales Invoice, setup hook)
- [x] Task 41 — DocType `Vietnam E Invoice Log`
- [x] Task 42 — Payload builder + adapter registry + mock adapter
- [x] Task 43 — Issuance orchestration on SI submit (opt-in, non-blocking, retry)
- [x] Task 44 — Điều chỉnh / thay thế flows (lineage on log)
- [ ] Task 45 — Real provider adapter + sandbox **[BLOCKED: OQ-1 — provider choice]**

### Checkpoint B — mock end-to-end green; only Task 45 remains for legal issuance

## Phase 16 — Khóa sổ & kết chuyển 911 (WS-D)
- [x] Task 46 — `period_close.py`: kết chuyển preview (pure, no writes)
- [x] Task 47 — Kết chuyển execute + Accounting Period lock (idempotent)
- [x] Task 48 — Runbook: month-end close section (docs)

## Phase 17 — Kê khai & export (WS-C2)
- [x] Task 49 — Bảng kê bán ra / mua vào export (CSV)
- [x] Task 50 — 01/GTGT XML export (HTKK/eTax, golden file)

## Phase 18 — GĐ2 remainder (WS-E)
- [x] Task 51 — TT45 khung khấu hao defaults on Asset Categories
- [x] Task 52 — Report Sổ chi tiết nguyên tệ + TK 007-style FX view
- [x] Task 53 — Per-employee TNCN surface (HRMS soft dependency, graceful degrade)

### Checkpoint C — all suites + 34 shipped VN tests green; migrate + pre-commit clean

## Phase 19 — Sửa sau kế hoạch (found while reviewing, after Task 53)
- [x] Task 54 — Tờ khai + bảng kê cùng cộng 133x (1331 HHDV + 1332 TSCĐ) → bảng kê khớp CT 24/25
- [x] Task 55 — HĐĐT: hóa đơn đã có số không phát hành lại (sửa qua điều chỉnh/thay thế)
- [x] Task 56 — Asset Category không bị treo bởi dòng của công ty đã xóa: VN setup tự dọn,
      `Company.on_trash` dọn dòng của chính nó (trước đó: không tạo được công ty VN mới)

## Gates (not code tasks)
- [ ] OQ-1: user chooses HĐĐT provider + provides sandbox credentials → unblocks Task 45
- [ ] OQ-2/OQ-3: kế toán trưởng confirms mid-year opening method + cutover date
- [ ] Real Miyano cutover actions (opening balances, period lock, live issuance):
      verified backup + explicit user confirmation — never automatic
