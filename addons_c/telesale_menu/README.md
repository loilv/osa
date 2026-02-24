# Telesale Menu

Modern grid home menu for Odoo 19.0 backend - Telesale project.

## Features

- **Grid App Launcher**: Grid-style app launcher with icons
- **Search/Filter**: Tìm kiếm nhanh các ứng dụng
- **App Icons**: Hiển thị icons cho từng app với màu sắc tương ứng
- **Responsive**: Tự động điều chỉnh trên mobile/tablet
- **Smooth Animations**: Chuyển động mượt mà
- **Custom Logo & Favicon**: Tùy chỉnh logo và favicon

## Installation

1. Copy module vào thư mục addons
2. Update Apps List trong Odoo
3. Install module "Telesale Menu"

## Configuration

Không cần cấu hình thêm. Module sẽ tự động thay thế menu mặc định bằng grid home menu.

## Customization

### Thay đổi màu sắc
Chỉnh sửa file `static/src/scss/telesale_menu.scss`:

```scss
$grid-bg: #d8d0db;             // Background grid
$text-color: #333;             // Màu text
```

## License

LGPL-3
