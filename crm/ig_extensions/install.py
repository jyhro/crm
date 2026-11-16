import frappe


def has_app_permission():
	return bool({"System Manager", "Sales Manager", "Sales User"} & set(frappe.get_roles()))


def apply_configuration():
	settings = frappe.get_single("FCRM Settings")
	settings.brand_name = "International Graphics"
	settings.brand_logo = "/assets/crm/images/international-graphics.png"
	settings.favicon = "/assets/crm/images/ig-monogram.svg"
	# Remove only the menu entry introduced by the abandoned separate frontend.
	for row in list(settings.dropdown_items):
		if row.name1 == "ig_workspace":
			settings.remove(row)
	settings.save(ignore_permissions=True)
	if not frappe.db.get_single_value("System Settings", "default_app"):
		frappe.db.set_single_value("System Settings", "default_app", "crm")
	frappe.clear_cache()
