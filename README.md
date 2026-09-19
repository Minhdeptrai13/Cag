# ⚔️ Garena Liên Quân Mobile (AOV) Multi-Checker Pro

Bộ công cụ kiểm tra tài khoản Garena Liên Quân Mobile chuyên sâu thế hệ mới, tích hợp kiến trúc **3-trong-1: CLI + Web UI + Desktop App**.

---

## 🌟 Tính Năng Nổi Bật

1. **Phân Tích Chuyên Sâu Liên Quân Mobile (AOV)**:
   - Rank hiện tại & số sao (Đồng, Bạc, Vàng, Bạch Kim, Kim Cương, Tinh Anh, Cao Thủ, Chiến Tướng, Thách Đấu).
   - Tên Ingame, Cấp độ tài khoản, Tình trạng khóa (Bị BAN).
   - Tổng số tướng & Tổng số trang phục sở hữu.
   - Nhận diện phân loại chính xác các bậc skin VIP: **Thứ Nguyên Vệ Thần / SSS**, **Hợp Tác Anime (Kimetsu no Yaiba, Bleach, SAO, Jujutsu Kaisen...)**, **SS Tuyệt Sắc**.
   - Thống kê Sò Garena còn lại trên Napthe.vn.

2. **Xác Định Tài Khoản Trắng Thông Tin (TTT)**:
   - Tự động kiểm tra trên hệ thống Bảo Mật Garena: SĐT, Email, CCCD/CMND, 2FA Authenticator, Facebook.
   - Tách riêng danh sách tài khoản **Acc Trắng** xuất file tức thì.
   - Hỗ trợ **mọi định dạng phân cách combo**: `user:pass`, `user|pass`, `user;pass`, `user/pass`, phím Tab hoặc khoảng trắng.

3. **3 Giao Diện Đa Nền Tảng**:
   - **CLI Thông Minh**: Điều khiển bằng phím mũi tên `↑` / `↓` trên PC, tự động nhận diện và chuyển sang nhập số khi chạy trên Điện thoại (Termux).
   - **Web UI Glassmorphism**: Giao diện tối màu Cyberpunk siêu đẹp, kéo thả file combo .txt, hiển thị thẻ trực quan, responsive cả PC lẫn Mobile (kết nối qua IP LAN).
   - **Desktop App**: Khởi chạy ứng dụng cửa sổ độc lập.

---

## 🚀 Hướng Dẫn Sử Dụng

### Cài đặt thư viện:
```bash
pip install -r requirements.txt
```

### Các cách khởi chạy:

1. **Menu Tương Tác (Khuyên Dùng)**:
   ```bash
   python main.py
   ```
2. **Mở Giao Diện Web**:
   ```bash
   python main.py --web
   ```
   *(Trình duyệt sẽ tự động mở tại `http://127.0.0.1:8080`. Bạn cũng có thể mở từ điện thoại bằng cách truy cập `http://<IP_MÁY_TÍNH>:8080`)*

3. **Mở Dưới Dạng Cửa Sổ Desktop App**:
   ```bash
   python main.py --app
   ```

4. **Mở Trực Tiếp CLI**:
   ```bash
   python main.py --cli
   ```

5. **Check Nhanh Bằng Dòng Lệnh**:
   ```bash
   # Check 1 tài khoản
   python main.py <taikhoan> <matkhau>

   # Check file combo với 10 luồng
   python main.py combo.txt 10
   ```

---

## 📁 Kết Quả Xuất File
Mọi kết quả check sẽ được tự động lưu trong thư mục `res/`:
- `res/acc_trang_ttt.txt`: Danh sách tài khoản Trắng Thông Tin.
- `res/hit_lienquan.txt`: Toàn bộ tài khoản đăng nhập thành công.
