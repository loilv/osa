import ast

from odoo import fields, models
from odoo.orm.domains import Domain


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    last_call_time = fields.Datetime(string="Lần gọi gần nhất", default=fields.Datetime.now)
    call_back_time = fields.Datetime(string="Ngày gọi lại", default=fields.Datetime.now)
    date_insurance = fields.Date(string="Thời hạn bảo hiểm", default=fields.Date.today())
    record_url = fields.Char(string='Ghi âm mới nhất')
    note = fields.Text('Mô tả')

    # ===== Thông tin cơ bản =====
    vehicle_type = fields.Char(string='Hạng xe')
    brand = fields.Char(string='Hãng xe')
    model = fields.Char(string='Hiệu xe')

    chassis_number = fields.Char(string='Số khung')
    engine_number = fields.Char(string='Số máy')

    seat_capacity = fields.Integer(string='Số chỗ')
    business_transport = fields.Boolean(string='Kinh doanh vận tải')

    last_registration_year = fields.Char(string='Năm đăng ký cuối cùng')
    manufacture_year = fields.Char(string='Năm sản xuất')
    manufacture_country = fields.Char(string='Nước sản xuất')

    color = fields.Char(string='Màu sơn')

    # ===== Thông số kỹ thuật =====
    cylinder_capacity = fields.Char(string='Dung tích xi lanh')
    fuel_type = fields.Char(string='Loại nhiên liệu')

    designed_payload = fields.Float(string='Khối lượng hàng chuyên chở thiết kế')
    allowed_people = fields.Integer(string='Số người cho phép chở')

    total_weight_design = fields.Float(string='Khối lượng toàn bộ theo thiết kế')
    towing_weight = fields.Float(string='Khối lượng kéo theo')

    axle_length = fields.Float(string='Chiều dài cơ sở')
    engine_power_rpm = fields.Char(string='Công suất theo vòng quay')

    container_size = fields.Char(string='Kích thước bao')

    # ===== Đăng kiểm =====
    inspection_certificate_no = fields.Char(string='Số phiếu kiểm định')
    inspection_serial = fields.Char(string='Số seri đăng kiểm')

    inspection_expiry_date = fields.Date(string='Ngày hết hạn đăng kiểm')
    inspection_issue_date = fields.Date(string='Ngày cấp đăng kiểm')

    # ===== Thông tin quản lý =====
    license_plate = fields.Char(string='Biển số')
    owner_name = fields.Char(string='Chủ xe')
    managing_unit = fields.Char(string='Đơn vị quản lý')
    registration_address = fields.Char(string='Địa chỉ đăng ký')

    # ===== Trạng thái cải tạo =====
    modified_status = fields.Selection([
        ('yes', 'Đã cải tạo'),
        ('no', 'Chưa cải tạo')
    ], string='Đã cải tạo hay chưa')

    # ===== Loại xe =====
    vehicle_category = fields.Char(string='Loại xe')

    # ===== Bổ sung theo ảnh =====

    payload_weight = fields.Float(string='Trọng tải (tấn)')

    first_registration_date = fields.Date(string='Ngày đăng ký lần đầu')
    last_registration_date = fields.Date(string='Ngày đăng ký cuối cùng')

    usage_purpose = fields.Char(string='Mục đích sử dụng')

    plate_type = fields.Char(string='Loại biển xe')

    estimated_value = fields.Monetary(
        string='Giá trị xe ước tính',
        currency_field='currency_id'
    )

    insurance_expiry_date = fields.Date(
        string='Thời điểm hết hạn bảo hiểm hiện tại'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id.id
    )

    care_history_ids = fields.One2many(
        'crm.lead.care.history', 'lead_id', string='Lịch sử chăm sóc'
    )

    def assign_tag(self):
        pass

    def make_order(self):
        pass

    def assign_agent(self):
        pass

    def action_chat_zalo(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("livechat_sidebar.livechat_sidebar_chat_action")
        livechat_channel_ids = self.env['im_livechat.channel.member.history'].search([
            ('partner_id', '=', self.id),
            ('livechat_member_type', '=', 'visitor'),
        ]).channel_id.ids
        action["domain"] = Domain.AND([
            ast.literal_eval(action["domain"]),
            [('id', 'in', livechat_channel_ids)]
        ])
        return action

    def get_lead(self):
        pass
