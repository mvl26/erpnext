<template>
  <div class="relative flex h-full flex-col" v-if="postId && discussion">
    <div class="mx-auto w-full max-w-3xl">
      <div class="pb-16">
        <div class="pb-2 pt-14 flex w-full items-center sticky top-0 z-[1] bg-surface-white">
          <UserProfileLink class="mr-3" :user="discussion.owner">
            <UserAvatar size="lg" :user="discussion.owner" />
          </UserProfileLink>
          <div class="flex flex-col md:block">
            <UserProfileLink
              class="text-base font-medium text-ink-gray-9 hover:text-ink-blue-3"
              :user="discussion.owner"
            >
              {{ $user(discussion.owner).full_name }}
              <span class="hidden md:inline text-ink-gray-8">&nbsp;&middot;&nbsp;</span>
            </UserProfileLink>
            <time
              class="text-base text-ink-gray-5"
              :datetime="discussion.creation"
              :title="$dayjs(discussion.creation)"
            >
              {{ $dayjs(discussion.creation).fromNow() }}
            </time>
          </div>
          <div class="ml-auto flex space-x-2">
            <Dropdown
              v-if="!readOnlyMode"
              class="ml-auto"
              placement="right"
              :button="{
                icon: 'more-horizontal',
                variant: 'ghost',
                label: 'Tùy chọn bài đăng',
              }"
              :options="actions"
            />
          </div>
        </div>
        <div :class="{ 'pb-4 mt-1': !editingPost }">
          <div class="flex items-start justify-between space-x-1">
            <h1 v-if="!editingPost" class="flex items-center text-2xl font-semibold">
              <Tooltip v-if="discussion.closed_at" text="Bài đăng này đã đóng">
                <LucideLock class="mr-2 h-4 w-4 text-ink-gray-7" :stroke-width="2" />
              </Tooltip>
              <span class="text-ink-gray-9">
                {{ discussion.title }}
              </span>
            </h1>
          </div>
          <div class="mt-2 flex items-center text-base" v-show="!editingPost">
            <DiscussionBreadcrumbs :discussion="discussion" />
            <span class="px-1.5 text-ink-gray-8">&middot;</span>
            <span class="text-ink-gray-5">
              {{
                discussion.participants_count == 1
                  ? `1 người tham gia`
                  : `${discussion.participants_count} người tham gia`
              }}
            </span>
          </div>
        </div>
        <div
          :class="{
            'rounded-lg border p-4 focus-within:border-outline-gray-3': editingPost,
          }"
        >
          <div v-if="editingPost" class="w-full">
            <div class="mb-2">
              <input
                v-if="editingPost"
                type="text"
                class="w-full rounded border-0 text-ink-gray-9 px-0 py-0.5 text-2xl font-semibold focus:ring-0"
                ref="title"
                v-model="discussion.title"
                placeholder="Tiêu đề"
                v-focus
              />
            </div>
          </div>
          <CommentEditor
            :value="discussion.content"
            @change="discussion.content = $event"
            :submitButtonProps="{
              variant: 'solid',
              onClick: () => {
                $resources.discussion.setValue.submit({
                  title: discussion.title,
                  content: discussion.content,
                })
                editingPost = false
              },
              loading: $resources.discussion.setValue.loading,
            }"
            :discardButtonProps="{
              onClick: () => {
                editingPost = false
                $resources.discussion.reload()
              },
            }"
            :editable="editingPost"
          />
        </div>
        <div class="mt-3">
          <Reactions
            doctype="GP Discussion"
            :name="discussion.name"
            v-model:reactions="discussion.reactions"
            :read-only-mode="readOnlyMode"
          />
        </div>
      </div>
      <CommentsArea
        doctype="GP Discussion"
        :name="discussion.name"
        :newCommentsFrom="discussion.last_unread_comment"
        :read-only-mode="readOnlyMode"
        :disable-new-comment="discussion.closed_at"
      />
      <Dialog
        :options="{
          title: 'Chuyển bài đăng sang nhóm khác',
        }"
        @close="
          () => {
            discussionMoveDialog.project = null
            $resources.discussion.moveToProject.reset()
          }
        "
        v-model="discussionMoveDialog.show"
      >
        <template #body-content>
          <Autocomplete
            :options="projectOptions"
            v-model="discussionMoveDialog.project"
            placeholder="Chọn nhóm"
          />
          <ErrorMessage class="mt-2" :message="$resources.discussion.moveToProject.error" />
        </template>
        <template #actions>
          <Button
            class="w-full"
            variant="solid"
            :loading="$resources.discussion.moveToProject.loading"
            @click="
              $resources.discussion.moveToProject.submit({
                project: discussionMoveDialog.project?.value,
              })
            "
          >
            {{
              discussionMoveDialog.project
                ? `Chuyển đến ${discussionMoveDialog.project.label}`
                : 'Chuyển'
            }}
          </Button>
        </template>
      </Dialog>
      <RevisionsDialog
        v-model="showRevisionsDialog"
        doctype="GP Discussion"
        :name="discussion.name"
        fieldname="content"
      />
    </div>
  </div>
</template>
<script>
import { Autocomplete, Dropdown, Dialog, Tooltip, call } from 'frappe-ui'
import Reactions from './Reactions.vue'
import CommentsArea from '@/components/CommentsArea.vue'
import CommentEditor from './CommentEditor.vue'
import TextEditor from '@/components/TextEditor.vue'
import UserProfileLink from './UserProfileLink.vue'
import DiscussionMeta from './DiscussionMeta.vue'
import DiscussionBreadcrumbs from './DiscussionBreadcrumbs.vue'
import RevisionsDialog from './RevisionsDialog.vue'
import { focus } from '@/directives'
import { copyToClipboard } from '@/utils'
import { activeTeams } from '@/data/teams'
import { getTeamProjects } from '@/data/projects'
import { nextTick } from 'vue'

export default {
  name: 'DiscussionView',
  props: ['postId', 'readOnlyMode'],
  directives: {
    focus,
  },
  components: {
    TextEditor,
    Reactions,
    CommentsArea,
    Dropdown,
    Dialog,
    Autocomplete,
    UserProfileLink,
    CommentEditor,
    Tooltip,
    DiscussionMeta,
    DiscussionBreadcrumbs,
    RevisionsDialog,
  },
  resources: {
    discussion() {
      return {
        type: 'document',
        doctype: 'GP Discussion',
        name: this.postId,
        realtime: true,
        whitelistedMethods: {
          trackVisit: 'track_visit',
          closeDiscussion: 'close_discussion',
          reopenDiscussion: 'reopen_discussion',
          pinDiscussion: 'pin_discussion',
          unpinDiscussion: 'unpin_discussion',
          addBookmark: 'add_bookmark',
          removeBookmark: 'remove_bookmark',
          moveToProject: {
            method: 'move_to_project',
            validate(params) {
              if (!params.args.project) {
                return 'Cần chọn nhóm để chuyển bài đăng này'
              }
            },
            onError() {
              this.discussionMoveDialog.show = true
            },
            onSuccess() {
              this.onDiscussionMove()
            },
          },
        },
        onSuccess(doc) {
          this.updateUrlSlug()
          if (
            !this.$route.query.comment &&
            !this.$route.query.poll &&
            !this.$route.query.fromSearch &&
            (doc.last_unread_comment || doc.last_unread_poll)
          ) {
            this.$router.replace({
              query: {
                comment: doc.last_unread_comment || undefined,
                poll: doc.last_unread_poll || undefined,
              },
            })
          }

          if (
            this.$route.name === 'ProjectDiscussion' &&
            Number(this.$route.params.postId) === doc.name
          ) {
            this.$resources.discussion.trackVisit.submit()
          }
        },
      }
    },
  },
  data() {
    return {
      editingPost: false,
      discussionMoveDialog: {
        show: false,
        project: null,
      },
      showRevisionsDialog: false,
      showNavbar: false,
    }
  },
  methods: {
    copyLink() {
      let location = window.location
      let url = `${location.origin}${location.pathname}`
      copyToClipboard(url)
    },
    onDiscussionMove() {
      this.$nextTick(() => {
        this.discussionMoveDialog.show = false
        this.discussionMoveDialog.project = null

        this.$router.replace({
          name: 'ProjectDiscussion',
          params: {
            teamId: this.discussion.team,
            projectId: this.discussion.project,
            postId: this.discussion.name,
          },
        })
      })
      this.$resources.discussion.moveToProject.reset()
    },
    updateUrlSlug() {
      let doc = this.discussion
      if (!this.$route.params.slug || this.$route.params.slug !== doc.slug) {
        nextTick(() => {
          this.$router.replace({
            name: 'ProjectDiscussion',
            params: { ...this.$route.params, slug: doc.slug },
            query: this.$route.query,
          })
        })
      }
    },
  },
  computed: {
    discussion() {
      return this.$resources.discussion.doc
    },
    projectOptions() {
      return activeTeams.value.map((team) => ({
        group: team.title,
        items: getTeamProjects(team.name).map((project) => ({
          label: project.title,
          value: project.name,
        })),
      }))
    },
    actions() {
      return [
        {
          label: 'Sửa',
          icon: 'edit',
          onClick: () => {
            this.editingPost = true
          },
        },
        {
          label: 'Phiên bản',
          icon: 'rotate-ccw',
          onClick: () => (this.showRevisionsDialog = true),
        },
        {
          label: 'Sao chép liên kết',
          icon: 'link',
          onClick: this.copyLink,
        },
        {
          label: 'Ghim bài đăng...',
          icon: 'arrow-up-left',
          condition: () => !this.discussion.pinned_at,
          onClick: () => {
            let project = this.$getDoc('GP Project', this.discussion.project)
            this.$dialog({
              title: 'Ghim bài đăng',
              message: `Khi được ghim, bài đăng sẽ hiển thị ở đầu danh sách bài đăng trong ${project.title}. Bạn có muốn ghim bài đăng này không?`,
              icon: { name: 'arrow-up-left' },
              actions: [
                {
                  label: 'Ghim',
                  onClick: (close) => this.$resources.discussion.pinDiscussion.submit().then(close),
                  variant: 'solid',
                },
              ],
            })
          },
        },
        {
          label: 'Bỏ ghim bài đăng...',
          icon: 'arrow-down-left',
          condition: () => this.discussion.pinned_at,
          onClick: () => {
            this.$dialog({
              title: 'Bỏ ghim bài đăng',
              message: `Bạn có muốn bỏ ghim bài đăng này không?`,
              icon: { name: 'arrow-down-left' },
              actions: [
                {
                  label: 'Bỏ ghim',
                  onClick: (close) =>
                    this.$resources.discussion.unpinDiscussion.submit().then(close),
                  variant: 'solid',
                },
              ],
            })
          },
        },
        {
          label: 'Đóng bài đăng...',
          icon: 'lock',
          condition: () => !this.discussion.closed_at,
          onClick: () => {
            this.$dialog({
              title: 'Đóng bài đăng',
              message:
                'Khi bài đăng bị đóng, mọi người sẽ không thể bình luận. Bất kỳ ai cũng có thể mở lại bài đăng sau. Bạn có muốn đóng bài đăng này không?',
              icon: { name: 'lock' },
              actions: [
                {
                  label: 'Đóng',
                  onClick: (close) =>
                    this.$resources.discussion.closeDiscussion.submit().then(close),
                  variant: 'solid',
                },
              ],
            })
          },
        },
        {
          label: 'Mở lại bài đăng...',
          icon: 'unlock',
          condition: () => this.discussion.closed_at,
          onClick: () => {
            this.$dialog({
              title: 'Mở lại bài đăng',
              message: 'Bạn có muốn mở lại bài đăng này không? Mọi người sẽ có thể bình luận trở lại.',
              icon: { name: 'unlock' },
              actions: [
                {
                  label: 'Mở lại',
                  onClick: (close) =>
                    this.$resources.discussion.reopenDiscussion.submit().then(close),
                  variant: 'solid',
                },
              ],
            })
          },
        },
        {
          label: 'Lưu bài',
          icon: 'bookmark',
          onClick: () => {
            this.$resources.discussion.addBookmark.submit()
          },
          condition: () => !this.discussion.is_bookmarked,
        },
        {
          label: 'Bỏ lưu bài',
          icon: 'bookmark',
          onClick: () => {
            this.$resources.discussion.removeBookmark.submit()
          },
          condition: () => this.discussion.is_bookmarked,
        },
        {
          label: 'Chuyển đến...',
          icon: 'log-out',
          onClick: () => {
            this.discussionMoveDialog.show = true
          },
        },
        {
          label: 'Xóa',
          icon: 'trash',
          onClick: () => {
            $dialog({
              title: 'Xóa',
              message: 'Bạn có chắc muốn xóa bài đăng này? Thao tác này không thể hoàn tác!',
              actions: [
                {
                  label: 'Xóa',
                  variant: 'solid',
                  theme: 'red',
                  onClick: ({ close }) => {
                    return this.$resources.discussion.delete.submit().then(() => {
                      this.$router.replace({ name: 'Project' })
                      close()
                    })
                  },
                },
              ],
            })
          },
        },
      ]
    },
  },
  pageMeta() {
    if (!this.discussion) return
    let project = this.$getDoc('GP Project', this.discussion.project)
    if (!project) return
    return {
      title: [this.discussion.title, project.title].filter(Boolean).join(' - '),
    }
  },
}
</script>
