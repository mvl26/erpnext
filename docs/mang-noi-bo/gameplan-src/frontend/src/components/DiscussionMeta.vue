<template>
  <div class="leading-5">
    <span class="text-base text-ink-gray-8">
      <UserProfileLink class="hover:text-ink-blue-3" :user="discussion.owner">
        {{ $user(discussion.owner).full_name }}
      </UserProfileLink>
      trong
      <DiscussionBreadcrumbs :discussion="discussion" />
    </span>
    <span> &middot; </span>
    <span class="text-base text-ink-gray-5">
      {{ `${discussion.participants_count} người tham gia` }}
    </span>
  </div>
</template>
<script>
import DiscussionBreadcrumbs from './DiscussionBreadcrumbs.vue'
import UserProfileLink from './UserProfileLink.vue'

export default {
  name: 'DiscussionMeta',
  props: ['discussion'],
  components: { UserProfileLink, DiscussionBreadcrumbs },
}
</script>
