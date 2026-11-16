import frappe


class FCRMSettingsAccess:
	@frappe.whitelist()
	def restore_defaults(self, force: bool = False):
		frappe.only_for("System Manager", True)
		return super().restore_defaults(force)


	@frappe.whitelist()
	def restore_demo_data(self):
		frappe.only_for("System Manager", True)
		return super().restore_demo_data()
