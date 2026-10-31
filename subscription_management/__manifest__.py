{
    "name": "Brightloop Subscription Management",
    "summary": "Manage recurring plans, subscriptions, billing, discounts and collections",
    "version": "17.0.1.0.0",
    "category": "Accounting/Subscriptions",
    "license": "LGPL-3",
    "depends": ["account", "auth_signup", "mail", "portal", "product", "sale_management"],
    "data": [
        "security/subscription_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/ir_cron.xml",
        "views/staff_views.xml",
        "views/subscription_views.xml",
        "views/portal_templates.xml",
    ],
    "application": True,
    "installable": True,
}

