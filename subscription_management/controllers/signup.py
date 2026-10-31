import re

from odoo import _, http
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.http import request


class BrightloopSignupPolicy(AuthSignupHome):
    @http.route()
    def web_auth_signup(self, *args, **kw):
        password = kw.get("password")
        if password:
            valid = (
                len(password) > 8
                and re.search(r"[A-Z]", password)
                and re.search(r"[a-z]", password)
                and re.search(r"[^A-Za-z0-9]", password)
            )
            if not valid:
                qcontext = self.get_auth_signup_qcontext()
                qcontext["error"] = _("Use a password longer than 8 characters with an uppercase letter, a lowercase letter, and a special character.")
                response = request.render("auth_signup.signup", qcontext)
                response.headers["X-Frame-Options"] = "SAMEORIGIN"
                response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
                return response
        return super().web_auth_signup(*args, **kw)

    @http.route()
    def web_auth_reset_password(self, *args, **kw):
        password = kw.get("password")
        if password:
            valid = (
                len(password) > 8
                and re.search(r"[A-Z]", password)
                and re.search(r"[a-z]", password)
                and re.search(r"[^A-Za-z0-9]", password)
            )
            if not valid:
                qcontext = self.get_auth_signup_qcontext()
                qcontext["error"] = _("Use a password longer than 8 characters with an uppercase letter, a lowercase letter, and a special character.")
                response = request.render("auth_signup.reset_password", qcontext)
                response.headers["X-Frame-Options"] = "SAMEORIGIN"
                response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
                return response
        return super().web_auth_reset_password(*args, **kw)

