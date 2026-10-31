from odoo import _, fields, models


class BrightloopStaffInvite(models.TransientModel):
    _name = "brightloop.staff.invite"
    _description = "Invite Subscription Staff"

    name = fields.Char(required=True)
    email = fields.Char(required=True)

    def action_invite(self):
        self.ensure_one()
        user = self.env["res.users"].sudo().with_context(no_reset_password=True).create({
            "name": self.name,
            "login": self.email.strip().lower(),
            "email": self.email.strip().lower(),
            "company_id": self.env.company.id,
            "company_ids": [(6, 0, [self.env.company.id])],
            "groups_id": [(6, 0, [self.env.ref("subscription_management.group_brightloop_staff").id])],
        })
        user.with_context(create_user=True).action_reset_password()
        return {"type": "ir.actions.act_window_close"}

