# Trust-Aware PYMK Recommendation Demo UI

Giao diện Web tương tác hiện đại cho hệ thống **Trust/Fraud Detection + People You May Know (PYMK) Recommendation**.

## ✨ Tính năng chính

1. **Dashboard Tổng quan (Overview)**
   - Thống kê tỷ lệ rủi ro botnet / fraud.
   - Biểu đồ phân bổ 4 tầng chính sách tín nhiệm (Tiers 1-4) và phổ điểm tín nhiệm (`S_trust`).
   - Danh sách tài khoản mẫu để kiểm thử nhanh.

2. **So sánh Can thiệp PYMK (PYMK Demo)**
   - Bảng so sánh trực quan song song (Side-by-side): Danh sách PYMK gốc (chưa can thiệp) vs Danh sách đã lọc / hạ bậc an toàn.
   - Hỗ trợ lựa chọn chính sách: `DROP` (Cách ly loại bỏ ứng viên nguy hiểm) hoặc `DOWNRANK` (Hạ bậc ưu tiên theo công thức hợp nhất).
   - Thanh trượt điều chỉnh ngưỡng bảo lãnh bạn chung (`mutual_tier1_threshold`) cho tài khoản Tier 3.

3. **Phân tích Tín nhiệm & Gian lận (Trust & Fraud Detection)**
   - Tra cứu hồ sơ rủi ro của bất kỳ User ID nào.
   - Biểu đồ radar trực quan 4 trụ cột tín nhiệm: Xác thực định danh (`S_auth`), Tương tác (`S_interact`), Vệ sinh mạng lưới (`S_network`), An toàn nội dung (`S_content`).
   - Chuỗi suy luận giải thích quyết định (Multi-step Reasoning Trace).

4. **Trực quan Mạng lưới (Network Explorer)**
   - Bản đồ đồ thị tương tác (Cytoscape.js) mô phỏng mạng lưới 2-hop xung quanh người dùng.
   - Mã màu trực quan theo 4 tầng chính sách tín nhiệm: Tier 1 (Xanh lá), Tier 2 (Xanh dương), Tier 3 (Vàng cam), Tier 4 (Đỏ nguy hiểm).

5. **Thông tin Kiến trúc & Thuật toán (System Architecture)**
   - Sơ đồ Pipeline tổng thể từ Offline Training, Nearline Serving đến Online Inference.
   - Bảng quy định công thức toán học & ngưỡng phân tầng chính sách.
   - Tài liệu API endpoints tích hợp.

## 🚀 Khởi chạy ứng dụng

### 1. Khởi chạy Backend (FastAPI)
```bash
# Từ thư mục gốc dự án
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Khởi chạy Frontend (React + Vite + Tailwind CSS)
```bash
cd frontend

# Cài đặt dependencies (nếu chưa cài)
npm install --legacy-peer-deps

# Chạy Development Server
npm run dev
```
Truy cập UI tại: [http://localhost:3000](http://localhost:3000)

### 3. Chế độ Mock Mode
- Có sẵn nút chuyển đổi **Live API / Mock Mode** ngay trên thanh Sidebar bên trái.
- Khi backend chưa bật, người dùng có thể kích hoạt Mock Mode để trải nghiệm toàn bộ tương tác và giao diện với dữ liệu mô phỏng theo phân phối thực tế của dataset Bitcoin-OTC / MGTAB.
