from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SubscriptionPlan(models.Model):
    _name = "brightloop.subscription.plan"
    _description = "Subscription Plan"
    _order = "sequence, name"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Html()
    billing_interval = fields.Selection(
        [("day", "Daily"), ("week", "Weekly"), ("month", "Monthly"), ("year", "Yearly")],
        required=True,
        default="month",
    )
    billing_count = fields.Integer(default=1, required=True)
    minimum_quantity = fields.Float(default=1.0, required=True)
    start_date = fields.Date()
    end_date = fields.Date()
    auto_close = fields.Boolean(default=True)
    allow_pause = fields.Boolean(default=True)
    allow_early_close = fields.Boolean(default=True)
    allow_renewal = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    subscription_count = fields.Integer(compute="_compute_subscription_count")

    @api.depends("name")
    def _compute_subscription_count(self):
        counts = self.env["brightloop.subscription"]._read_group(
            [("plan_id", "in", self.ids)], ["plan_id"], ["__count"]
        )
        mapped = {plan.id: count for plan, count in counts}
        for plan in self:
            plan.subscription_count = mapped.get(plan.id, 0)

    @api.constrains("billing_count", "minimum_quantity", "start_date", "end_date")
    def _check_plan_values(self):
        for plan in self:
            if plan.billing_count < 1 or plan.minimum_quantity <= 0:
                raise ValidationError(_("Billing frequency and minimum quantity must be positive."))
            if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
                raise ValidationError(_("The plan end date must be on or after its start date."))


class SubscriptionDiscount(models.Model):
    _name = "brightloop.subscription.discount"
    _description = "Subscription Discount Rule"
    _order = "start_date desc, name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    discount_type = fields.Selection(
        [("percent", "Percentage"), ("fixed", "Fixed amount")], required=True, default="percent"
    )
    value = fields.Float(required=True)
    applies_to = fields.Selection(
        [("subscription", "Whole subscription"), ("products", "Selected products")],
        required=True,
        default="subscription",
    )
    product_ids = fields.Many2many("product.product", string="Products")
    minimum_amount = fields.Monetary(currency_field="currency_id", default=0)
    minimum_quantity = fields.Float(default=0)
    start_date = fields.Date()
    end_date = fields.Date()
    usage_limit = fields.Integer(help="Leave at zero for unlimited uses.")
    used_count = fields.Integer(readonly=True, default=0)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.company.currency_id)

    @api.constrains("value", "discount_type", "usage_limit", "start_date", "end_date")
    def _check_discount_values(self):
        for rule in self:
            if rule.value <= 0 or (rule.discount_type == "percent" and rule.value > 100):
                raise ValidationError(_("Enter a percentage from 0 to 100 or a positive fixed amount."))
            if rule.start_date and rule.end_date and rule.end_date < rule.start_date:
                raise ValidationError(_("The discount end date must be on or after its start date."))
            if rule.usage_limit < 0:
                raise ValidationError(_("The usage limit cannot be negative."))

    def is_available(self, on_date=None):
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        return bool(
            self.active
            and (not self.start_date or self.start_date <= on_date)
            and (not self.end_date or self.end_date >= on_date)
            and (not self.usage_limit or self.used_count < self.usage_limit)
        )


class Subscription(models.Model):
    _name = "brightloop.subscription"
    _description = "Customer Subscription"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "start_date desc, id desc"

    name = fields.Char(required=True, copy=False, default="New", tracking=True, index=True)
    partner_id = fields.Many2one("res.partner", required=True, tracking=True, index=True)
    plan_id = fields.Many2one("brightloop.subscription.plan", required=True, tracking=True)
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    payment_term_id = fields.Many2one("account.payment.term")
    quotation_template_id = fields.Many2one("sale.order.template", string="Quotation Template")
    quotation_validity_days = fields.Integer(default=30)
    quotation_valid_until = fields.Date(compute="_compute_quotation_valid_until")
    start_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(tracking=True)
    next_invoice_date = fields.Date(index=True)
    state = fields.Selection(
        [("draft", "Draft"), ("quotation", "Quotation"), ("confirmed", "Confirmed"),
         ("active", "Active"), ("paused", "Paused"), ("closed", "Closed")],
        required=True, default="draft", tracking=True, index=True,
    )
    line_ids = fields.One2many("brightloop.subscription.line", "subscription_id", copy=True)
    invoice_ids = fields.One2many("account.move", "brightloop_subscription_id", string="Invoices")
    discount_id = fields.Many2one("brightloop.subscription.discount", string="Discount")
    amount_untaxed = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_tax = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_total = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    amount_paid = fields.Monetary(compute="_compute_collection", currency_field="currency_id")
    amount_due = fields.Monetary(compute="_compute_collection", currency_field="currency_id")
    invoice_count = fields.Integer(compute="_compute_collection")
    invoice_status = fields.Selection(
        [("none", "No invoices"), ("paid", "Paid"), ("due", "Outstanding"), ("overdue", "Overdue")],
        compute="_compute_collection", store=True,
    )
    notes = fields.Html()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("brightloop.subscription") or "New"
        return super().create(vals_list)

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax", "line_ids.price_total")
    def _compute_amounts(self):
        for subscription in self:
            subscription.amount_untaxed = sum(subscription.line_ids.mapped("price_subtotal"))
            subscription.amount_tax = sum(subscription.line_ids.mapped("price_tax"))
            subscription.amount_total = sum(subscription.line_ids.mapped("price_total"))

    @api.depends("start_date", "quotation_validity_days")
    def _compute_quotation_valid_until(self):
        for subscription in self:
            subscription.quotation_valid_until = subscription.start_date + relativedelta(days=subscription.quotation_validity_days) if subscription.start_date else False

    @api.onchange("quotation_template_id")
    def _onchange_quotation_template_id(self):
        for subscription in self:
            if not subscription.quotation_template_id:
                continue
            commands = [(5, 0, 0)]
            for template_line in subscription.quotation_template_id.sale_order_template_line_ids:
                commands.append((0, 0, {
                    "product_id": template_line.product_id.id,
                    "name": template_line.name,
                    "quantity": template_line.product_uom_qty,
                    "price_unit": template_line.price_unit,
                    "tax_ids": [(6, 0, template_line.tax_id.ids)],
                }))
            subscription.line_ids = commands

    @api.depends("invoice_ids.payment_state", "invoice_ids.invoice_date_due", "invoice_ids.amount_residual", "invoice_ids.brightloop_payment_ids.amount")
    def _compute_collection(self):
        today = fields.Date.context_today(self)
        for subscription in self:
            invoices = subscription.invoice_ids.filtered(lambda move: move.state == "posted")
            subscription.invoice_count = len(invoices)
            subscription.amount_paid = sum(invoices.mapped("brightloop_paid_amount"))
            subscription.amount_due = sum(max(move.amount_residual - move.brightloop_paid_amount, 0.0) for move in invoices)
            if not invoices:
                subscription.invoice_status = "none"
            elif any(move.invoice_date_due and move.invoice_date_due < today and move.amount_residual - move.brightloop_paid_amount > 0 for move in invoices):
                subscription.invoice_status = "overdue"
            elif subscription.amount_due > 0:
                subscription.invoice_status = "due"
            else:
                subscription.invoice_status = "paid"

    @api.constrains("start_date", "end_date", "plan_id", "line_ids")
    def _check_dates_and_quantity(self):
        for subscription in self:
            if subscription.end_date and subscription.end_date < subscription.start_date:
                raise ValidationError(_("The expiry date must be on or after the start date."))
            quantity = sum(subscription.line_ids.mapped("quantity"))
            if subscription.line_ids and quantity < subscription.plan_id.minimum_quantity:
                raise ValidationError(_("This plan requires a minimum quantity of %s.") % subscription.plan_id.minimum_quantity)

    def action_to_quotation(self):
        self.write({"state": "quotation"})

    def action_confirm(self):
        for subscription in self:
            if not subscription.line_ids:
                raise UserError(_("Add at least one product before confirming the subscription."))
            if subscription.plan_id.start_date and subscription.start_date < subscription.plan_id.start_date:
                raise UserError(_("This plan is not available yet."))
            if subscription.plan_id.end_date and subscription.start_date > subscription.plan_id.end_date:
                raise UserError(_("This plan is no longer available."))
            if subscription.state == "quotation" and subscription.quotation_valid_until < fields.Date.context_today(self):
                raise UserError(_("This quotation has expired. Update its start date or create a new quotation."))
            subscription.write({"state": "confirmed", "next_invoice_date": subscription.start_date})

    def action_activate(self):
        self.write({"state": "active"})

    def action_pause(self):
        for subscription in self:
            if not subscription.plan_id.allow_pause:
                raise UserError(_("Pausing is disabled for this plan."))
            subscription.state = "paused"

    def action_resume(self):
        self.write({"state": "active"})

    def action_close(self):
        for subscription in self:
            if not subscription.plan_id.allow_early_close and (not subscription.end_date or subscription.end_date > fields.Date.context_today(self)):
                raise UserError(_("Early closure is disabled for this plan."))
            subscription.state = "closed"

    def action_renew(self):
        renewed = self.browse()
        for subscription in self:
            if not subscription.plan_id.allow_renewal:
                raise UserError(_("Renewals are disabled for this plan."))
            renewed |= subscription.copy({"name": "New", "state": "draft", "start_date": subscription.end_date or fields.Date.context_today(self), "end_date": False, "next_invoice_date": False})
        return {
            "type": "ir.actions.act_window", "name": _("Renewed Subscriptions"),
            "res_model": self._name, "view_mode": "list,form", "domain": [("id", "in", renewed.ids)],
        }

    def _advance_date(self, date_value):
        self.ensure_one()
        delta = {"day": "days", "week": "weeks", "month": "months", "year": "years"}[self.plan_id.billing_interval]
        return date_value + relativedelta(**{delta: self.plan_id.billing_count})

    def action_generate_invoice(self):
        for subscription in self:
            if subscription.state not in ("confirmed", "active"):
                raise UserError(_("Only confirmed or active subscriptions can be invoiced."))
            period_start = subscription.next_invoice_date or subscription.start_date
            if subscription.end_date and period_start > subscription.end_date:
                subscription.state = "closed"
                continue
            period_end = subscription._advance_date(period_start)
            if subscription.end_date:
                period_end = min(period_end, subscription.end_date)
            if self.env["account.move"].search_count([
                ("brightloop_subscription_id", "=", subscription.id),
                ("brightloop_period_start", "=", period_start),
                ("state", "!=", "cancel"),
            ]):
                subscription.next_invoice_date = period_end
                continue
            invoice_lines = []
            for line in subscription.line_ids:
                invoice_lines.append((0, 0, {
                    "product_id": line.product_id.id,
                    "name": line.name or line.product_id.display_name,
                    "quantity": line.quantity,
                    "price_unit": line.price_unit,
                    "tax_ids": [(6, 0, line.tax_ids.ids)],
                }))
            if subscription.discount_id and subscription.discount_id.is_available(period_start):
                discount = subscription.discount_id
                if subscription.amount_untaxed >= discount.minimum_amount and sum(subscription.line_ids.mapped("quantity")) >= discount.minimum_quantity:
                    eligible = subscription.line_ids.filtered(lambda line: discount.applies_to == "subscription" or line.product_id in discount.product_ids)
                    eligible_amount = sum(eligible.mapped("price_subtotal"))
                    if discount.discount_type == "percent":
                        discount_amount = eligible_amount * discount.value / 100
                    else:
                        discount_amount = min(discount.value, eligible_amount)
                    if discount_amount:
                        invoice_lines.append((0, 0, {"name": _("Discount: %s") % discount.name, "quantity": 1, "price_unit": -discount_amount, "tax_ids": []}))
                        discount.used_count += 1
            invoice = self.env["account.move"].create({
                "move_type": "out_invoice", "partner_id": subscription.partner_id.id,
                "invoice_date": period_start,
                "invoice_payment_term_id": subscription.payment_term_id.id,
                "invoice_origin": subscription.name,
                "brightloop_subscription_id": subscription.id,
                "brightloop_period_start": period_start,
                "brightloop_period_end": period_end,
                "invoice_line_ids": invoice_lines,
            })
            subscription.next_invoice_date = period_end
            if subscription.state == "confirmed":
                subscription.state = "active"
            return {
                "type": "ir.actions.act_window", "res_model": "account.move", "res_id": invoice.id,
                "view_mode": "form", "target": "current",
            }
        return True

    @api.model
    def _cron_generate_due_invoices(self):
        today = fields.Date.today()
        due = self.search([("state", "in", ["confirmed", "active"]), ("next_invoice_date", "<=", today)], limit=500)
        for subscription in due:
            if subscription.end_date and subscription.next_invoice_date > subscription.end_date and subscription.plan_id.auto_close:
                subscription.state = "closed"
                continue
            subscription.action_generate_invoice()

    @api.model
    def _cron_close_expired(self):
        today = fields.Date.today()
        expired = self.search([
            ("state", "in", ["confirmed", "active", "paused"]),
            ("end_date", "<", today),
            ("plan_id.auto_close", "=", True),
        ])
        expired.write({"state": "closed"})

    def _compute_access_url(self):
        super()._compute_access_url()
        for subscription in self:
            subscription.access_url = "/my/subscriptions/%s" % subscription.id


class SubscriptionLine(models.Model):
    _name = "brightloop.subscription.line"
    _description = "Subscription Product Line"

    subscription_id = fields.Many2one("brightloop.subscription", required=True, ondelete="cascade", index=True)
    product_id = fields.Many2one("product.product", required=True, domain=[("sale_ok", "=", True)])
    name = fields.Char()
    quantity = fields.Float(default=1, required=True)
    price_unit = fields.Float(required=True)
    tax_ids = fields.Many2many("account.tax", domain=[("type_tax_use", "=", "sale")])
    currency_id = fields.Many2one(related="subscription_id.currency_id", store=True)
    price_subtotal = fields.Monetary(compute="_compute_amount", store=True, currency_field="currency_id")
    price_tax = fields.Monetary(compute="_compute_amount", store=True, currency_field="currency_id")
    price_total = fields.Monetary(compute="_compute_amount", store=True, currency_field="currency_id")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.name = line.product_id.get_product_multiline_description_sale()
                line.price_unit = line.product_id.lst_price
                line.tax_ids = line.product_id.taxes_id.filtered(lambda tax: tax.company_id == line.subscription_id.company_id)

    @api.depends("quantity", "price_unit", "tax_ids")
    def _compute_amount(self):
        for line in self:
            taxes = line.tax_ids.compute_all(line.price_unit, line.currency_id, line.quantity, product=line.product_id)
            line.price_subtotal = taxes["total_excluded"]
            line.price_total = taxes["total_included"]
            line.price_tax = line.price_total - line.price_subtotal

    @api.constrains("quantity", "price_unit")
    def _check_line_values(self):
        for line in self:
            if line.quantity <= 0 or line.price_unit < 0:
                raise ValidationError(_("Quantity must be positive and unit price cannot be negative."))


class AccountMove(models.Model):
    _inherit = "account.move"

    brightloop_subscription_id = fields.Many2one("brightloop.subscription", copy=False, index=True)
    brightloop_period_start = fields.Date(copy=False, index=True)
    brightloop_period_end = fields.Date(copy=False)
    brightloop_payment_ids = fields.One2many("brightloop.subscription.payment", "invoice_id", string="Recorded Payments")
    brightloop_paid_amount = fields.Monetary(compute="_compute_brightloop_paid", currency_field="currency_id")

    @api.depends("brightloop_payment_ids.amount")
    def _compute_brightloop_paid(self):
        for move in self:
            move.brightloop_paid_amount = sum(move.brightloop_payment_ids.mapped("amount"))


class SubscriptionPayment(models.Model):
    _name = "brightloop.subscription.payment"
    _description = "Recorded Subscription Payment"
    _order = "payment_date desc, id desc"

    name = fields.Char(required=True, default=lambda self: fields.Date.today().strftime("PAY/%Y/%m/%d"))
    invoice_id = fields.Many2one("account.move", required=True, domain=[("move_type", "=", "out_invoice")], ondelete="cascade", index=True)
    subscription_id = fields.Many2one(related="invoice_id.brightloop_subscription_id", store=True, index=True)
    partner_id = fields.Many2one(related="invoice_id.partner_id", store=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", store=True)
    amount = fields.Monetary(required=True, currency_field="currency_id")
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    payment_method = fields.Selection(
        [("bank", "Bank transfer"), ("card", "Card"), ("cash", "Cash"), ("other", "Other")],
        required=True, default="bank",
    )
    note = fields.Char()

    @api.constrains("amount", "invoice_id")
    def _check_payment_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError(_("Payment amount must be positive."))
            if payment.invoice_id.move_type != "out_invoice":
                raise ValidationError(_("Payments can only be recorded against customer invoices."))
            previous = sum(payment.invoice_id.brightloop_payment_ids.filtered(lambda item: item != payment).mapped("amount"))
            if previous + payment.amount > payment.invoice_id.amount_total:
                raise ValidationError(_("Recorded payments cannot exceed the invoice total."))

