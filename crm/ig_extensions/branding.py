"""Identity sourced from igraphicspr.com; CRM Brand Settings remain an override."""

import frappe


def website_context(context):
	request = getattr(frappe.local, "request", None)
	if not request or request.path.strip("/") not in {"login", "update-password", "reset-password"}:
		return
	settings = frappe.get_cached_doc("FCRM Settings")
	return {
		"app_name": settings.brand_name or "International Graphics",
		"logo": settings.brand_logo or "/assets/crm/images/international-graphics.png",
		"favicon": settings.favicon or "/assets/crm/images/ig-monogram.svg",
		"title": "International Graphics · Acceso al CRM",
		"show_footer_on_login": 0,
	}
