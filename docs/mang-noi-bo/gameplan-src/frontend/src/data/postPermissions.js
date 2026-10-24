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

export function isMiyanoAdmin() {
  return Boolean(postPermissions.data?.is_admin)
}
