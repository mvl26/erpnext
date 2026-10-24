<template>
  <div class="relative flex items-center text-p-base">
    <div
      class="mr-3 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-ink-gray-9"
    >
      <LucideLock class="h-4 w-4" v-if="activity.action === 'Discussion Closed'" />
      <LucideUnlock class="h-4 w-4" v-else-if="activity.action === 'Discussion Reopened'" />
      <LucideEdit3 class="h-4 w-4" v-else-if="activity.action === 'Discussion Title Changed'" />
      <LucideArrowUpLeft class="h-4 w-4" v-else-if="activity.action === 'Discussion Pinned'" />
      <LucideArrowDownLeft class="h-4 w-4" v-else-if="activity.action === 'Discussion Unpinned'" />
      <LucideEdit3 class="h-4 w-4" v-else-if="activity.action === 'Task Value Changed'" />
    </div>
    <p>
      <UserInfo :email="activity.user" v-slot="{ user }">
        <UserProfileLink
          class="font-medium text-ink-gray-8 hover:text-ink-gray-5"
          :user="user.name"
        >
          {{ user.full_name }}
        </UserProfileLink>
      </UserInfo>
      <span class="text-ink-gray-9" v-if="activity.action == 'Discussion Closed'">
        đã đóng bài đăng này
      </span>
      <span class="text-ink-gray-9" v-if="activity.action == 'Discussion Reopened'">
        đã mở lại bài đăng này
      </span>
      <span class="text-ink-gray-9" v-if="activity.action == 'Discussion Pinned'">
        đã ghim bài đăng này
      </span>
      <span class="text-ink-gray-9" v-if="activity.action == 'Discussion Unpinned'">
        đã bỏ ghim bài đăng này
      </span>
      <span class="text-ink-gray-9" v-if="activity.action == 'Discussion Title Changed'">
        đã đổi tiêu đề từ "{{ activity.data.old_title }}" thành "{{ activity.data.new_title }}"
      </span>
      <span class="text-ink-gray-5" v-if="activity.action == 'Task Value Changed'">
        <template v-if="activity.data.field === 'assigned_to'">
          đã giao việc này cho
          <UserProfileLink
            class="font-medium text-ink-gray-8 hover:text-ink-gray-5"
            :user="$user(activity.data.new_value).name"
          >
            {{ $user(activity.data.new_value).full_name }}
          </UserProfileLink>
        </template>
        <template v-else-if="activity.data.field === 'description'">
          đã cập nhật mô tả
        </template>
        <template v-else-if="activity.data.field === 'project'">
          đã đổi nhóm
          <span v-if="activity.data.old_value">từ&nbsp;</span>
          <span class="text-ink-gray-8">
            {{ projectTitle(activity.data.old_value) }}
          </span>
          sang
          <span class="text-ink-gray-8">
            {{ projectTitle(activity.data.new_value) }}
          </span>
        </template>
        <template v-else>
          đã đổi {{ fieldLabel(activity.data) }}
          <span v-if="activity.data.old_value">từ&nbsp;</span>
          <span class="text-ink-gray-8">{{
            displayValue(activity.data.field, activity.data.old_value)
          }}</span>
          thành
          <span class="text-ink-gray-8">{{
            displayValue(activity.data.field, activity.data.new_value)
          }}</span>
        </template> </span
      >&nbsp;<time
        class="text-ink-gray-5"
        :datetime="activity.creation"
        :title="$dayjs(activity.creation)"
      >
        {{ $dayjs(activity.creation).fromNow() }}
      </time>
    </p>
  </div>
</template>
<script>
import UserProfileLink from './UserProfileLink.vue'
import { projectTitle } from '@/utils/formatters'

// display-only labels; stored field names / values stay unchanged
const fieldLabels = {
  title: 'tiêu đề',
  description: 'mô tả',
  status: 'trạng thái',
  priority: 'mức ưu tiên',
  assigned_to: 'người phụ trách',
  due_date: 'hạn chót',
  project: 'nhóm',
}
const valueLabels = {
  status: {
    Backlog: 'Tồn đọng',
    Todo: 'Cần làm',
    'In Progress': 'Đang làm',
    Done: 'Hoàn thành',
    Canceled: 'Đã hủy',
  },
  priority: {
    Low: 'Thấp',
    Medium: 'Trung bình',
    High: 'Cao',
    Urgent: 'Khẩn',
  },
}

export default {
  name: 'Activity',
  props: {
    activity: {
      type: Object,
      required: true,
    },
  },
  components: { UserProfileLink },
  methods: {
    projectTitle,
    fieldLabel(data) {
      return fieldLabels[data.field] || data.field_label
    },
    displayValue(field, value) {
      return valueLabels[field]?.[value] ?? value
    },
  },
}
</script>
