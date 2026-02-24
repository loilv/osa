# Asterisk Connector for Odoo 19

Module tích hợp Odoo với hệ thống tổng đài Asterisk PBX.

## Tính năng

### 1. Quay số (Click-to-call)
- Gọi trực tiếp từ form liên hệ (res.partner)
- Bàn phím số trên giao diện web
- Tự động ghi lại lịch sử cuộc gọi

### 2. Nhận cuộc gọi
- Popup tự động khi có cuộc gọi đến
- Hiển thị thông tin khách hàng (nếu có trong hệ thống)
- Âm báo chuông điện thoại
- Browser notification

### 3. Chuyển cuộc gọi
- Chuyển cuộc gọi đến extension khác
- Danh sách extension có thể chuyển

### 4. Lịch sử cuộc gọi
- Xem tất cả cuộc gọi đi/đến
- Lọc theo ngày, trạng thái, hướng cuộc gọi
- Gọi lại từ lịch sử

## Cài đặt

### Yêu cầu
- Odoo 19.0
- Asterisk PBX với AMI (Asterisk Manager Interface) được bật
- Python package: `websocket-client`

### Bước 1: Cài đặt module
```bash
pip install websocket-client
```

Sau đó restart Odoo và cài đặt module từ Apps.

### Bước 2: Cấu hình Asterisk Server
1. Vào menu **Điện thoại > Cấu hình > Asterisk Servers**
2. Tạo server mới với thông tin:
   - **Host/IP**: Địa chỉ Asterisk server
   - **AMI Port**: Port của AMI (mặc định 5038)
   - **AMI Username**: Username đã cấu hình trong `manager.conf`
   - **AMI Password**: Password tương ứng
3. Click "Kiểm tra kết nối" để test

### Bước 3: Cấu hình User Extension
1. Vào menu **Điện thoại > Cấu hình > User Extensions**
2. Gán extension cho từng user Odoo:
   - Chọn user Odoo
   - Chọn server
   - Nhập số extension
   - Chọn loại channel (SIP/PJSIP/IAX2)

### Bước 4: Phân quyền
Thêm users vào nhóm:
- **Asterisk User**: Có thể sử dụng tính năng gọi điện
- **Asterisk Manager**: Quản lý cấu hình server và users

## Cấu hình Asterisk

### manager.conf
Thêm user AMI trong `/etc/asterisk/manager.conf`:

```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[odoo]
secret = your_password
read = all
write = all
deny = 0.0.0.0/0.0.0.0
permit = your_odoo_server_ip/255.255.255.255
```

### Webhook cho cuộc gọi đến (Tùy chọn)
Để nhận cuộc gọi đến realtime, cần cấu hình Asterisk gửi event tới Odoo.

Tạo AGI script hoặc sử dụng ARI để gọi webhook:
```
POST /asterisk/ami_event
Content-Type: application/json

{
    "event": "Ringing",
    "CallerIDNum": "0901234567",
    "CallerIDName": "John Doe",
    "Exten": "100",
    "Channel": "PJSIP/100-00000001",
    "Uniqueid": "1234567890.1"
}
```

## Sử dụng

### Gọi điện
1. Click icon điện thoại trên systray (góc phải trên)
2. Nhập số và nhấn nút gọi
3. Hoặc click nút "Gọi điện" trên form liên hệ

### Nhận cuộc gọi
- Popup tự động hiển thị khi có cuộc gọi đến
- Click "Trả lời" hoặc "Từ chối"

### Chuyển cuộc gọi
1. Trong panel cuộc gọi đang hoạt động, click icon chuyển
2. Chọn extension muốn chuyển đến

## API Endpoints

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/asterisk/make_call` | POST | Thực hiện cuộc gọi |
| `/asterisk/transfer_call` | POST | Chuyển cuộc gọi |
| `/asterisk/hangup` | POST | Kết thúc cuộc gọi |
| `/asterisk/get_user_config` | POST | Lấy cấu hình user |
| `/asterisk/get_call_history` | POST | Lấy lịch sử cuộc gọi |
| `/asterisk/ami_event` | POST | Webhook nhận event AMI |

## Troubleshooting

### Không kết nối được AMI
- Kiểm tra firewall cho phép port AMI
- Kiểm tra `manager.conf` có permit đúng IP
- Kiểm tra username/password

### Không nhận được cuộc gọi đến
- Cần cấu hình webhook từ Asterisk
- Kiểm tra extension đã được gán cho user

### Không có âm thanh
- Browser cần cho phép quyền phát âm thanh
- Cho phép notification trong browser settings

## License

LGPL-3

## Author

Odoo Community
