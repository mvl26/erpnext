<template>
  <div class="pt-6">
    <div class="rounded-lg border p-4">
      <div class="mb-3 flex items-center space-x-2">
        <UserProfileLink :user="$user().name">
          <UserAvatar size="lg" :user="$user().name" />
        </UserProfileLink>
        <div class="flex w-full items-center">
          <div>
            <span class="text-base text-ink-gray-9">
              <UserProfileLink class="font-medium hover:text-ink-blue-3" :user="$user().name">
                {{ $user().full_name }}
              </UserProfileLink>
              trong
              <router-link
                class="hover:text-ink-blue-3"
                :to="{
                  name: 'Team',
                  params: {
                    teamId: project.doc.team,
                  },
                }"
              >
                {{ $getDoc('GP Team', project.doc.team)?.title || project.doc.team }}
              </router-link>
              <span class="text-ink-gray-4"> &mdash; </span>
              <router-link
                class="hover:text-ink-blue-3"
                :to="{
                  name: 'Project',
                  params: {
                    teamId: project.doc.team,
                    projectId: project.doc.name,
                  },
                }"
              >
                {{ project.doc.title }}
              </router-link>
            </span>
          </div>
        </div>
        <div class="hidden shrink-0 space-x-2 sm:block">
          <Button @click="discard">Bỏ</Button>
          <Button
            variant="solid"
            :disabled="!canPost"
            :loading="$resources.newDiscussion.loading"
            @click="publish"
          >
            Đăng
          </Button>
        </div>
      </div>
      <div
        v-if="!canPost"
        class="mb-3 rounded-md bg-surface-amber-1 px-3 py-2 text-base text-ink-amber-3"
      >
        Bạn chưa có quyền đăng bài trong nhóm này. Bạn vẫn có thể đọc và bình luận các bài đăng.
      </div>
      <ErrorMessage :message="$resources.newDiscussion.error" />
      <textarea
        class="mt-1 w-full resize-none border-0 px-0 py-0.5 text-3xl font-bold placeholder-ink-gray-3 focus:ring-0"
        v-model="title"
        placeholder="Tiêu đề"
        rows="1"
        wrap="soft"
        maxlength="140"
        v-focus
        @keydown.enter.prevent="$refs.textEditor.editor.commands.focus()"
        @input="
          (e) => {
            e.target.style.height = e.target.scrollHeight + 'px'
          }
        "
        @change="(e) => saveDraftPost({ title: e.target.value })"
      ></textarea>
      <TextEditor
        ref="textEditor"
        class="mt-1"
        editor-class="rounded-b-lg max-w-[unset] prose-sm h-[calc(100vh-340px)] sm:h-[calc(100vh-250px)] overflow-auto"
        :content="content"
        @change="onNewPostChange"
        placeholder="Viết nội dung..."
      >
        <template v-slot:bottom>
          <div class="mt-2 flex flex-col justify-between sm:flex-row sm:items-center">
            <div class="flex items-center overflow-x-auto">
              <TextEditorFixedMenu class="overflow-x-auto" :buttons="textEditorMenuButtons" />
              <AttachFileButton class="shrink-0" :getEditor="() => $refs.textEditor?.editor" />
            </div>
            <div class="mt-2 shrink-0 space-x-2 text-right sm:hidden">
              <Button @click="discard">Bỏ</Button>
              <Button
                variant="solid"
                :disabled="!canPost"
                :loading="$resources.newDiscussion.loading"
                @click="publish"
              >
                Đăng
              </Button>
            </div>
          </div>
        </template>
      </TextEditor>
    </div>
  </div>
</template>
<script>
import TextEditor from '@/components/TextEditor.vue'
import { focus } from '@/directives'
import UserProfileLink from '@/components/UserProfileLink.vue'
import TextEditorFixedMenu from 'frappe-ui/src/components/TextEditor/TextEditorFixedMenu.vue'
import AttachFileButton from '@/components/AttachFileButton.vue'
import { canPostIn } from '@/data/postPermissions'

export default {
  name: 'ProjectDiscussionNew',
  props: ['project'],
  components: { TextEditor, UserProfileLink, TextEditorFixedMenu, AttachFileButton },
  directives: { focus },
  data() {
    let draftPost = this.getDraftPost()
    return {
      title: draftPost?.title || '',
      content: draftPost?.content || '',
    }
  },
  resources: {
    newDiscussion() {
      return {
        url: 'frappe.client.insert',
        makeParams({ title, content }) {
          return {
            doc: {
              doctype: 'GP Discussion',
              project: this.project.doc.name,
              title,
              content,
            },
          }
        },
        validate(params) {
          if (!params.doc.title) {
            return `Vui lòng nhập tiêu đề trước khi đăng.`
          }
        },
        onSuccess(doc) {
          this.$router.replace({
            name: 'ProjectDiscussion',
            params: {
              teamId: doc.team,
              projectId: doc.project,
              postId: doc.name,
            },
          })
          this.title = ''
          this.content = ''
        },
      }
    },
  },
  methods: {
    onNewPostChange(value) {
      this.content = value
      this.saveDraftPost({ content: value })
    },
    publish() {
      this.$resources.newDiscussion.submit(
        {
          title: this.title,
          content: this.content,
        },
        {
          onSuccess() {
            this.clearDraftPost()
          },
        },
      )
    },
    discard() {
      if (!this.$refs.textEditor.editor.isEmpty || this.title) {
        this.$dialog({
          title: 'Bỏ bài đăng',
          message: 'Bạn có chắc muốn bỏ bài đăng này?',
          actions: [
            {
              label: 'Bỏ bài đăng',
              onClick: (close) => {
                localStorage.removeItem(this.draftPostKey())
                this.$router.push({ name: 'ProjectDiscussions' })
                close()
              },
              variant: 'solid',
            },
            {
              label: 'Giữ lại',
            },
          ],
        })
      } else {
        localStorage.removeItem(this.draftPostKey())
        this.$router.push({ name: 'ProjectDiscussions' })
      }
    },
    saveDraftPost({ title, content }) {
      setTimeout(() => {
        let draftPost = this.getDraftPost()
        if (!draftPost) {
          draftPost = {}
        }
        if (title != null) {
          draftPost.title = title
        }
        if (content != null) {
          draftPost.content = content
        }
        localStorage.setItem(this.draftPostKey(), JSON.stringify(draftPost))
      }, 0)
    },
    getDraftPost() {
      let draftPost = localStorage.getItem(this.draftPostKey())
      return draftPost ? JSON.parse(draftPost) : null
    },
    clearDraftPost() {
      localStorage.removeItem(this.draftPostKey())
    },
    draftPostKey() {
      return `draft-post-${this.project.doc.name}`
    },
  },
  computed: {
    canPost() {
      return canPostIn(this.project.doc.name)
    },
    textEditorMenuButtons() {
      return [
        'Paragraph',
        ['Heading 2', 'Heading 3', 'Heading 4', 'Heading 5', 'Heading 6'],
        'Separator',
        'Bold',
        'Italic',
        'Separator',
        'Bullet List',
        'Numbered List',
        'Separator',
        'Align Left',
        'Align Center',
        'Align Right',
        'FontColor',
        'Separator',
        'Image',
        'Video',
        'Link',
        'Blockquote',
        'Code',
        'Horizontal Rule',
        [
          'InsertTable',
          'AddColumnBefore',
          'AddColumnAfter',
          'DeleteColumn',
          'AddRowBefore',
          'AddRowAfter',
          'DeleteRow',
          'MergeCells',
          'SplitCell',
          'ToggleHeaderColumn',
          'ToggleHeaderRow',
          'ToggleHeaderCell',
          'DeleteTable',
        ],
        'Separator',
        'Undo',
        'Redo',
      ]
    },
  },
}
</script>
