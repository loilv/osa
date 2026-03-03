import logging

from odoo import Command, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    last_call_time = fields.Datetime(string="Lần gọi gần nhất")
    call_back_time = fields.Datetime(string="Ngày gọi lại")
    date_insurance = fields.Date(string="Ngày hết hạn bảo hiểm")
    record_url = fields.Char(string='Ghi âm mới nhất')
    note = fields.Text('Mô tả')
    phone = fields.Char('Điện thoại',
        compute='_compute_phone', inverse='_inverse_phone', readonly=False, store=True)
    date_of_birth = fields.Date(related='partner_id.date_of_birth')
    gender = fields.Selection(related='partner_id.gender')
    stage_note = fields.Text('Ghi chú')

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
    assign_history_ids = fields.One2many('crm.history.assign', 'lead_id', string='Lịch sử phân công')

    def action_call(self):
        """Gửi bus notification để JS gọi ra qua asterisk_phone service."""
        self.ensure_one()
        phone = (self.phone or '').strip()
        if not phone:
            raise UserError('Lead chưa có số điện thoại.')

        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'telesale_crm/make_call',
            {'phone': phone},
        )

    def assign_tag(self):
        pass

    def make_order(self):
        pass

    def action_consultant(self):
        self.stage_id = self.env.ref('telesale_crm.stage_consultant').id

    def create_care_history(self):
        self.env['crm.lead.care.history'].create({
            'lead_id': self.id,
            'date_callback': self.call_back_time,
            'stage_id': self.stage_id.id,
            'note': self.stage_note,
            'lost_reason_id': self.lost_reason_id.id,
            'user_id': self.env.user.id,
        })

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            self.create_care_history()
        return res

    def action_chat_zalo(self):
        """Directly open a chat window for this lead's phone number."""
        self.ensure_one()
        phone = (self.phone or '').strip()
        if not phone:
            return

        # Zalo lookup for name
        zalo_name = phone
        ZaloAccount = self.env.get('zalo.account')
        account = None
        zalo_id = False
        if ZaloAccount is not None:
            account = ZaloAccount.sudo().search([
                ('user_ids', 'in', [self.env.uid]),
                ('state', '=', 'connected'),
            ], limit=1)
            if not account:
                account = ZaloAccount.sudo().search([
                    ('state', '=', 'connected'),
                ], limit=1)
            if account:
                try:
                    find_result = account._call_bridge(
                        'find-user', method='POST', data={'phone': phone},
                    )
                    if find_result.get('success'):
                        user_data = find_result.get('data', {})
                        zalo_name = (
                            user_data.get('display_name', '')
                            or user_data.get('zalo_name', '')
                            or phone
                        )
                        zalo_id = user_data.get('uid', '')
                except Exception as e:
                    _logger.warning('Zalo lookup failed for %s: %s', phone, e)

        # Find or create partner
        partner = self.env['res.partner'].sudo().search([('phone', '=', phone)], limit=1)
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': zalo_name,
                'phone': phone,
            })

        operator = self.env.user.partner_id

        # Check for existing open session
        existing_channel = self.env['discuss.channel'].sudo().search([
            ('channel_type', '=', 'livechat'),
            ('channel_member_ids.partner_id', '=', partner.id),
            ('livechat_end_dt', '=', False),
        ], order='create_date desc', limit=1)

        if existing_channel:
            channel = existing_channel
        else:
            livechat_channel = self.env['im_livechat.channel'].sudo().search([
                ('user_ids', 'in', [self.env.uid]),
            ], limit=1)
            if not livechat_channel:
                livechat_channel = self.env['im_livechat.channel'].sudo().search([], limit=1)
            if not livechat_channel:
                return

            channel = self.env['discuss.channel'].sudo().create({
                'channel_member_ids': [
                    Command.create({
                        'partner_id': operator.id,
                        'livechat_member_type': 'agent',
                    }),
                    Command.create({
                        'partner_id': partner.id,
                        'livechat_member_type': 'visitor',
                    }),
                ],
                'livechat_operator_id': operator.id,
                'livechat_channel_id': livechat_channel.id,
                'livechat_status': 'in_progress',
                'channel_type': 'livechat',
                'name': zalo_name,
            })
            channel._broadcast([operator.id])

            # Link Zalo thread if possible
            if account and zalo_id:
                try:
                    partner.sudo().write({'zalo_uid': zalo_id})
                    channel.sudo().write({
                        'zalo_thread_id': zalo_id,
                        'zalo_account_id': account.id,
                    })
                except Exception as e:
                    _logger.warning('Could not link Zalo for %s: %s', phone, e)

        # Notify frontend to open ChatWindow via bus
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'telesale_crm/open_chat_window',
            {'channel_id': channel.id},
        )

    def action_send_friend_request_zalo(self):
        """Open the Zalo friend request wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zalo.chat.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def get_lead(self):
        domain = [('user_id', '=', self.env.uid), ('stage_id.is_new', '=', True)]
        new_lead = self.env['crm.lead'].sudo().search(domain, limit=1)
        if new_lead:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': "Vui lòng xử lý hết số lượng Cơ hội 'Mới' hiện có trước khi yêu cầu Lấy thêm số.",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        domain_all = [('stage_id.is_new', '=', True)]
        new_public = self.env['crm.lead'].sudo().search(domain_all, limit=1)
        if not new_public:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': "Kho chung hiện tại đã hết cơ hội cung cấp. Vui lòng quay lại sau.",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        new_public.write({'user_id': self.env.uid})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': 'Thành công',
                'message': 'Đã nhận thành công 1 khách hàng mới từ Kho!',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
