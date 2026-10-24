// Miyano: quyền đăng bài theo nhóm
import { createResource } from 'frappe-ui'

export let postPermissions = createResource({
  url: 'gameplan.miyano.api.get_post_permissions',
  cache: 'Miyano Post Permissions',
  initialData: { is_admin: false, projects: {} },
  auto: true,
})

export function canPostIn(project) {
  if (!project) return true
  let data = postPermissions.data || {}
  if (data.is_admin) return true
  let value = data.projects?.[String(project)]
  // chưa tải xong -> tạm cho phép, máy chủ vẫn kiểm tra lại khi đăng
  return value === undefined ? true : value
}

// Chỉ quản trị viên, HCNS, Ban lãnh đạo hoặc người được cấp quyền mới tạo được nhóm / không gian
export function canCreateGroup() {
  let data = postPermissions.data || {}
  return Boolean(data.is_admin || data.can_create_group)
}

export function isMiyanoAdmin() {
  return Boolean(postPermissions.data?.is_admin)
}
