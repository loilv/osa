from odoo import fields, models

class InheritIrMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def init(self):
        crm_menu_sales = self.env.ref('crm.crm_menu_sales')
        menu_crm_opportunities = self.env.ref('crm.menu_crm_opportunities')
        crm_lead_menu_my_activities = self.env.ref('crm.crm_lead_menu_my_activities')

        if crm_menu_sales:
            crm_menu_sales.with_context(lang='vi_VN').write({
                'name': 'Cơ hội'
            })
        if menu_crm_opportunities:
            menu_crm_opportunities.with_context(lang='vi_VN').write({
                'name': 'Cơ hội cần xử lý'
            })
        if crm_lead_menu_my_activities:
            crm_lead_menu_my_activities.with_context(lang='vi_VN').write({
                'name': 'Cơ hội của tôi'
            })
        return super(InheritIrMenu, self).init()