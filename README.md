# Brightloop Subscription Management for Odoo

An Odoo 17 addon for the Brightloop Software subscription workflow in the hackathon brief. It manages recurring plans, product lines, subscription lifecycle, invoice generation, discount rules, payment records, and a customer self-service portal.

## Install

1. Copy `subscription_management/` into an Odoo 17 addons path.
2. Restart Odoo and update the Apps list.
3. Install **Brightloop Subscription Management**.
4. Assign **Subscription Staff** or **Subscription Administrator** under Settings → Users. Only administrators can edit plans and discounts; Odoo's own user administration controls who can add staff.
5. Configure products, sale taxes, and payment terms in the standard Odoo apps. Product attribute values and their extra prices use Odoo's standard product variant feature.

The addon uses Odoo's normal account invoices and payment terms. A daily scheduled action generates one invoice for each subscription that is due and advances its next billing date. The same invoice-period key is checked before creation to avoid duplicate bills. Expired plans can close subscriptions automatically. Staff can also use **Invoice Now** on a confirmed or active subscription.

## Included

- Daily, weekly, monthly, and yearly plans, availability windows, minimum quantities, and configurable pause, early close, renewal, and auto-close behavior.
- Draft → Quotation → Confirmed → Active → Closed lifecycle, numbered subscription records, quotation templates with validity windows, product quantities, prices, sale taxes, and payment terms.
- Automatic invoices using Odoo's accounting engine and tax configuration; invoice list views highlight overdue balances.
- Admin-managed percentage or fixed discount rules with product scope, minimum purchase and quantity, validity window, and usage limits.
- Payment records linked to customer invoices, with method, amount, date, and note; Odoo accounting remains the source of truth for posted and reconciled payments.
- Internal staff and administrator groups, portal record rules scoped to the customer's commercial partner, and read-only portal subscription and invoice views.
- Search filters and group-by views for active, outstanding, overdue, plan, status, and salesperson reporting.

## Notes

Odoo supplies account login, unique user logins, password reset emails, email delivery, tax computation, and accounting reconciliation. Configure outgoing mail and portal access in Odoo. Product and plan setup should be completed before confirming customer subscriptions. Recorded payment entries are operational tracking records; reconcile incoming cash through Odoo Accounting to update native invoice payment state.

