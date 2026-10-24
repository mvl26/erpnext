<template>
  <div class="flex flex-col">
    <router-view v-slot="{ Component, route }">
      <header
        class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-5 py-2.5"
        v-if="!route.meta?.hideHeader"
      >
        <Breadcrumbs class="h-7" :items="breadcrumbs">
          <template #prefix="{ item }">
            <span class="mr-2 flex rounded-sm text-2xl leading-none" v-if="item.icon">
              {{ item.icon }}
            </span>
          </template>
        </Breadcrumbs>
        <div v-if="$route.name === 'ProjectOverview'" class="flex items-center space-x-2">
          <Tooltip
            v-if="project.doc.is_private"
            text="Nhóm này chỉ hiển thị với thành viên không gian"
          >
            <Badge size="lg">
              <template #prefix><LucideLock class="w-3" /></template>
              Riêng tư
            </Badge>
          </Tooltip>
          <Badge size="lg" v-if="project.doc.archived_at">
            <template #prefix><LucideArchive class="w-3" /></template>
            Đã lưu trữ
          </Badge>
          <template v-if="!isMobile">
            <Button
              v-if="project.doc.is_followed"
              @click="project.unfollow.submit()"
              :loading="project.unfollow.loading"
            >
              <template #prefix><LucideBell class="w-4" /></template>
              Đang theo dõi
            </Button>
            <Button v-else @click="project.follow.submit()" :loading="project.follow.loading">
              <template #prefix><LucideBellPlus class="w-4" /></template>
              Theo dõi
            </Button>
          </template>
          <Dropdown
            v-if="$user().isNotGuest"
            placement="left"
            :button="{
              icon: 'more-horizontal',
              variant: 'ghost',
              label: 'Tùy chọn',
            }"
            :options="[
              {
                label: 'Sửa',
                icon: 'edit',
                onClick: () => (projectEditDialog.show = true),
                condition: () => !project.doc.archived_at,
              },
              {
                label: 'Theo dõi',
                icon: 'plus',
                onClick: () => project.follow.submit(),
                condition: () => isMobile && !project.doc.is_followed,
              },
              {
                label: 'Đang theo dõi',
                icon: 'check',
                onClick: () => project.unfollow.submit(),
                condition: () => isMobile && project.doc.is_followed,
              },
              {
                label: 'Quyền đăng bài & thông báo',
                icon: 'shield',
                onClick: () => openPostingSettings(project.doc.name),
                condition: () => isMiyanoAdmin(),
              },
              {
                label: 'Quản lý khách',
                icon: 'user-plus',
                onClick: () => (inviteGuestDialog.show = true),
                condition: () => !project.doc.archived_at,
              },
              {
                label: 'Chuyển sang không gian khác',
                icon: 'log-out',
                onClick: () => (projectMoveDialog.show = true),
                condition: () => !project.doc.archived_at,
              },
              {
                label: 'Gộp với nhóm khác',
                icon: LucideMerge,
                onClick: () => (projectMergeDialog.show = true),
              },
              {
                label: 'Lưu trữ nhóm này',
                icon: 'trash-2',
                onClick: archiveProject,
                condition: () => !project.doc.archived_at,
              },
              {
                label: 'Bỏ lưu trữ nhóm này',
                icon: 'trash-2',
                onClick: unarchiveProject,
                condition: () => project.doc.archived_at,
              },
            ]"
          />
        </div>
        <Dialog
          :options="{
            title: 'Sửa nhóm',
            actions: [
              {
                label: 'Lưu',
                variant: 'solid',
                onClick({ close }) {
                  return project.setValue
                    .submit({
                      title: project.doc.title,
                      is_private: project.doc.is_private,
                    })
                    .then(close)
                },
              },
            ],
          }"
          v-model="projectEditDialog.show"
        >
          <template #body-content>
            <FormControl
              class="mb-2"
              label="Tiêu đề"
              v-model="project.doc.title"
              placeholder="Tiêu đề nhóm"
            />
            <FormControl
              v-if="!team.doc.is_private"
              label="Chế độ hiển thị"
              type="select"
              :options="[
                { label: 'Mọi người đều thấy', value: 0 },
                { label: 'Chỉ thành viên không gian thấy (Riêng tư)', value: 1 },
              ]"
              v-model="project.doc.is_private"
            />
            <ErrorMessage class="mt-2" :message="project.setValue.error" />
          </template>
        </Dialog>
        <Dialog
          :options="{
            title: 'Chuyển nhóm sang không gian khác',
          }"
          @close="
            () => {
              projectMoveDialog.team = null
              project.moveToTeam.reset()
            }
          "
          v-model="projectMoveDialog.show"
        >
          <template #body-content>
            <Autocomplete
              :options="moveToTeamsList"
              v-model="projectMoveDialog.team"
              placeholder="Chọn không gian"
            >
              <template #item-prefix="{ option }">
                <span class="mr-2">{{ option.icon }}</span>
              </template>
            </Autocomplete>
            <ErrorMessage class="mt-2" :message="project.moveToTeam.error" />
          </template>
          <template #actions>
            <Button
              class="w-full"
              variant="solid"
              :loading="project.moveToTeam.loading"
              @click="
                () => {
                  project.moveToTeam.submit(
                    { team: projectMoveDialog.team?.value },
                    {
                      validate() {
                        if (!projectMoveDialog.team?.value) {
                          return 'Cần chọn không gian để chuyển nhóm này'
                        }
                      },
                      onSuccess() {
                        onProjectMove()
                      },
                    },
                  )
                }
              "
            >
              {{ projectMoveDialog.team ? `Chuyển sang ${projectMoveDialog.team.label}` : 'Chuyển' }}
            </Button>
          </template>
        </Dialog>
        <Dialog
          :options="{
            title: 'Gộp với nhóm khác',
          }"
          @close="
            () => {
              projectMergeDialog.project = null
              project.mergeWithProject.reset()
            }
          "
          v-model="projectMergeDialog.show"
        >
          <template #body-content>
            <p class="text-p-base text-ink-gray-8 mb-4">
              Thao tác này sẽ chuyển toàn bộ bài đăng, công việc và tài liệu từ nhóm
              <span class="whitespace-nowrap font-semibold">{{ project.doc.title }}</span>
              sang nhóm được chọn. Không thể hoàn tác thay đổi này!
            </p>
            {{ projectMergeDialog.project }}
            <Autocomplete
              :options="mergeProjectsList"
              v-model="projectMergeDialog.project"
              placeholder="Chọn nhóm"
            >
              <template #item-prefix="{ option }">
                <span class="mr-2">{{ option.icon }}</span>
              </template>
            </Autocomplete>
            <ErrorMessage class="mt-2" :message="project.mergeWithProject.error" />
          </template>
          <template #actions>
            <Button
              class="w-full"
              variant="solid"
              :loading="project.mergeWithProject.loading"
              @click="
                () => {
                  project.mergeWithProject.submit(
                    { project: projectMergeDialog.project?.value },
                    {
                      validate() {
                        if (!projectMergeDialog.project?.value) {
                          return 'Vui lòng chọn nhóm để gộp'
                        }
                      },
                      onSuccess() {
                        if (projectMergeDialog.project.value) {
                          projectMergeDialog.show = false
                          return $router.replace({
                            name: 'Project',
                            params: { projectId: projectMergeDialog.project.value },
                          })
                        }
                      },
                    },
                  )
                }
              "
            >
              {{
                projectMergeDialog.project
                  ? `Gộp với ${projectMergeDialog.project.label}`
                  : 'Gộp'
              }}
            </Button>
          </template>
        </Dialog>
        <InviteGuestDialog
          v-if="$user().isNotGuest"
          v-model="inviteGuestDialog.show"
          :project="project"
        />
      </header>

      <component
        v-if="project"
        :is="Component"
        :class="{ 'mx-auto w-full max-w-4xl px-5': !route.meta?.fullWidth }"
        :project="project"
        :team="team"
      />
    </router-view>
  </div>
</template>
<script>
import { computed } from 'vue'
import {
  Autocomplete,
  Dropdown,
  FormControl,
  Breadcrumbs,
  frappeRequest,
  Input,
  Tooltip,
  Select,
  Textarea,
} from 'frappe-ui'
import Pie from '@/components/Pie.vue'
import IconPicker from '@/components/IconPicker.vue'
import Links from '@/components/Links.vue'
import Tabs from '@/components/Tabs.vue'
import InviteGuestDialog from '@/components/InviteGuestDialog.vue'
import { projects } from '@/data/projects'
import { activeTeams, teams } from '@/data/teams'
import PinIcon from '~icons/lucide/pin'
import LucideMerge from '~icons/lucide/merge'
import { useScreenSize } from '@/utils/composables'
import { isMiyanoAdmin } from '@/data/postPermissions'

export default {
  name: 'Project',
  props: ['team', 'project'],
  components: {
    Input,
    Dropdown,
    Pie,
    IconPicker,
    Links,
    Tabs,
    Autocomplete,
    Tooltip,
    InviteGuestDialog,
    FormControl,
    Select,
    Textarea,
    Breadcrumbs,
  },
  setup() {
    const size = useScreenSize()
    const isMobile = computed(() => size.width < 640)
    return {
      PinIcon,
      LucideMerge,
      isMobile,
      isMiyanoAdmin,
      openPostingSettings: (name) => window.open(`/app/gp-project/${name}`, '_blank'),
    }
  },
  data() {
    return {
      projectMoveDialog: { show: false, team: null },
      projectEditDialog: { show: false },
      inviteGuestDialog: { show: false },
      projectMergeDialog: { show: false, project: null },
    }
  },
  computed: {
    moveToTeamsList() {
      return activeTeams.value
        .filter((d) => d.name != this.team.name)
        .map((d) => ({
          label: d.title,
          value: d.name,
          icon: d.icon,
        }))
    },
    mergeProjectsList() {
      return projects.data
        .filter((d) => d.name != this.project.name)
        .map((d) => ({
          label: d.title,
          value: d.name.toString(),
          icon: d.icon,
        }))
    },
    task() {
      let task = null
      if (this.$route.name === 'ProjectTaskDetail') {
        task = this.$getDocumentResource('GP Task', this.$route.params.taskId)
      }
      return task
    },
    breadcrumbs() {
      let items = [
        {
          label: this.team.doc.title,
          icon: this.team.doc.icon,
          route: { name: 'Team', params: { teamId: this.team.doc.name } },
        },
        {
          label: this.project.doc.title,
          route: {
            name: 'Project',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
            },
          },
        },
      ]
      if (
        ['ProjectDiscussions', 'ProjectDiscussion', 'ProjectDiscussionNew'].includes(
          this.$route.name,
        )
      ) {
        items.push({
          label: 'Bài đăng',
          route: {
            name: 'ProjectDiscussions',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
            },
          },
        })
      }
      if (this.$route.name === 'ProjectDiscussion') {
        let discussion = this.$getDocumentResource('GP Discussion', this.$route.params.postId)
        items.push({
          label: discussion?.doc?.title || this.$route.params.postId,
          route: {
            name: 'ProjectDiscussion',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
              postId: this.$route.params.postId,
            },
          },
        })
      }
      if (this.$route.name === 'ProjectDiscussionNew') {
        items.push({
          label: 'Bài đăng mới',
          route: {
            name: 'ProjectDiscussionNew',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
            },
          },
        })
      }

      if (['ProjectTasks', 'ProjectTaskDetail'].includes(this.$route.name)) {
        items.push({
          label: 'Công việc',
          route: {
            name: 'ProjectTasks',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
            },
          },
        })
      }

      if (this.$route.name === 'ProjectTaskDetail') {
        let task = this.$getDocumentResource('GP Task', this.$route.params.taskId)
        items.push({
          label: task?.doc?.title || this.$route.params.taskId,
          route: {
            name: 'ProjectTaskDetail',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
              taskId: this.$route.params.taskId,
            },
          },
        })
      }

      if (['ProjectPages', 'ProjectPage'].includes(this.$route.name)) {
        items.push({
          label: 'Tài liệu',
          route: {
            name: 'ProjectPages',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
            },
          },
        })
      }

      if (this.$route.name === 'ProjectPage') {
        let page = this.$getDocumentResource('GP Page', this.$route.params.pageId)
        items.push({
          label: page?.doc?.title || this.$route.params.pageId,
          route: {
            name: 'ProjectPage',
            params: {
              teamId: this.team.doc.name,
              projectId: this.project.doc.name,
              pageId: this.$route.params.pageId,
            },
          },
        })
      }

      return items
    },
  },
  methods: {
    archiveProject() {
      this.$dialog({
        title: 'Lưu trữ nhóm',
        message: 'Bạn có chắc chắn muốn lưu trữ nhóm này?',
        actions: [
          {
            label: 'Lưu trữ',
            variant: 'solid',
            onClick: (close) => {
              return this.project.archive.submit(null, {
                onSuccess: close,
              })
            },
          },
        ],
      })
    },
    unarchiveProject() {
      this.$dialog({
        title: 'Bỏ lưu trữ nhóm',
        message: 'Bạn có chắc chắn muốn bỏ lưu trữ nhóm này?',
        actions: [
          {
            label: 'Bỏ lưu trữ',
            variant: 'solid',
            onClick: (close) => {
              return this.project.unarchive.submit(null, {
                onSuccess: close,
              })
            },
          },
          {
            label: 'Hủy',
          },
        ],
      })
    },
    onProjectMove() {
      this.projectMoveDialog.show = false
      projects.reload()
      for (let team of teams.data || []) {
        if ([this.team.doc.name, this.projectMoveDialog.team.value].includes(team.name)) {
          if (this.projectMoveDialog.team.value === team.name) {
            team.open = true
          }
        }
      }
      this.$router.push({
        name: 'ProjectOverview',
        params: {
          teamId: this.projectMoveDialog.team.value,
          projectId: this.project.name,
        },
      })
      this.projectMoveDialog.team = null
      this.project.moveToTeam.reset()
    },
  },
}
</script>
