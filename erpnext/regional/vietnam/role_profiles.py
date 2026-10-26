# Copyright (c) 2026, Công ty TNHH Miyano Việt Nam

"""Vietnam go-live: the retired department Role Profiles.

C3 (RBAC): ``ensure_vn_role_profiles()`` is gone. The Role Profiles a deployment assigns
to real users are now the matrix's ``RP-*`` profiles, created by
``erpnext.access.permissions.sync`` (``bench --site miyano execute
erpnext.access.permissions.sync.run``). ``VN_ROLE_PROFILES`` stays only as the list of
OLD profile names so the cutover can drop them from users and from the site.
"""

# Retired Role Profile (tiếng Việt) -> the standard ERPNext roles it used to grant.
VN_ROLE_PROFILES = {
	"Kế toán": ["Accounts User"],
	"Kế toán trưởng": ["Accounts Manager", "Accounts User"],
	"Thủ kho": ["Stock User"],
	"Bán hàng": ["Sales User"],
	"Mua hàng": ["Purchase User"],
	"Quản lý": ["Accounts Manager", "Sales Manager", "Purchase Manager", "Stock Manager"],
}
