from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager


class BrightloopPortal(CustomerPortal):
    @http.route(["/my/subscriptions", "/my/subscriptions/page/<int:page>"], type="http", auth="user", website=True)
    def portal_subscriptions(self, page=1, **kwargs):
        domain = [("partner_id", "=", request.env.user.partner_id.commercial_partner_id.id)]
        model = request.env["brightloop.subscription"].with_user(request.env.user)
        total = model.search_count(domain)
        pager_data = pager(url="/my/subscriptions", total=total, page=page, step=20)
        subscriptions = model.search(domain, order="start_date desc", limit=20, offset=pager_data["offset"])
        values = self._prepare_portal_layout_values()
        values.update({"subscriptions": subscriptions, "pager": pager_data, "page_name": "subscriptions"})
        return request.render("subscription_management.portal_subscription_list", values)

    @http.route("/my/subscriptions/<int:subscription_id>", type="http", auth="user", website=True)
    def portal_subscription(self, subscription_id, **kwargs):
        subscription = request.env["brightloop.subscription"].with_user(request.env.user).browse(subscription_id)
        if not subscription.exists() or subscription.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
            return request.not_found()
        values = self._prepare_portal_layout_values()
        values.update({"subscription": subscription, "page_name": "subscription"})
        return request.render("subscription_management.portal_subscription", values)

