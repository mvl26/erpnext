<template>
  <div class="pt-6">
    <div class="space-y-5 pb-40">
      <ProjectOverviewReadme :project="project" />
      <div class="sm:rounded sm:border sm:px-4 sm:py-3">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-ink-gray-8">Bài đăng</h2>
          <Button :route="{ name: 'ProjectDiscussions' }">Xem tất cả</Button>
        </div>
        <DiscussionList
          :listOptions="{
            filters: { project: project.doc.name },
            pageLength: 4,
          }"
          :hideLoadMore="true"
        />
      </div>
      <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div class="sm:rounded sm:border sm:px-4 sm:py-3">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-xl font-semibold text-ink-gray-8">Công việc</h2>
            <Button :route="{ name: 'ProjectTasks' }">Xem tất cả</Button>
          </div>
          <TaskList
            :listOptions="{
              filters: {
                project: project.doc.name,
                status: ['in', ['Backlog', 'Todo', 'In Progress']],
              },
              pageLength: 4,
            }"
          />
        </div>
        <div class="sm:rounded sm:border sm:px-4 sm:py-3">
          <div class="mb-3 flex items-center justify-between">
            <h2 class="text-xl font-semibold text-ink-gray-8">Tài liệu</h2>
            <Button :route="{ name: 'ProjectPages' }">Xem tất cả</Button>
          </div>
          <PageList
            :listOptions="{
              filters: {
                project: project.doc.name,
              },
              pageLength: 4,
            }"
          />
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import ProjectOverviewReadme from './ProjectOverviewReadme.vue'

export default {
  name: 'ProjectOverview',
  props: ['project'],
  components: {
    ProjectOverviewReadme,
  },
}
</script>
