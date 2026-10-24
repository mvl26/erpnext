<template>
  <FileUploader
    :uploadArgs="{ private: true }"
    :validateFile="validateFile"
    @success="onSuccess"
    @failure="onFailure"
  >
    <template v-slot="{ uploading, progress, openFileSelector }">
      <Button
        variant="ghost"
        :loading="uploading"
        @click="openFileSelector"
        :title="'Đính kèm tệp (PDF, Word, Excel, ảnh...)'"
      >
        <template #prefix><LucidePaperclip class="h-4 w-4" /></template>
        {{ uploading ? `Đang tải ${progress}%` : label }}
      </Button>
    </template>
  </FileUploader>
</template>
<script>
// Miyano: nút đính kèm tệp vào bài đăng / bình luận.
// Tệp tải lên ở chế độ riêng tư; khi lưu bài, máy chủ gắn tệp vào bài để người đọc bài mở được.
import { FileUploader } from 'frappe-ui'

const MAX_MB = 25

export default {
  name: 'AttachFileButton',
  props: {
    getEditor: { type: Function, default: null },
    label: { type: String, default: 'Đính kèm' },
  },
  emits: ['attached'],
  components: { FileUploader },
  methods: {
    validateFile(file) {
      if (file.size > MAX_MB * 1024 * 1024) {
        return `Tệp quá lớn (tối đa ${MAX_MB} MB)`
      }
    },
    escape(text) {
      let div = document.createElement('div')
      div.innerText = text
      return div.innerHTML
    },
    onSuccess(file) {
      let editor = this.getEditor ? this.getEditor() : null
      let name = this.escape(file.file_name)
      let isImage = /\.(png|jpe?g|gif|webp)$/i.test(file.file_name || '')
      let html = isImage
        ? `<img src="${file.file_url}" alt="${name}">`
        : `<p><a href="${file.file_url}" target="_blank" rel="noopener">📎 ${name}</a></p>`
      if (editor) {
        let chain = editor.chain().focus().insertContent(html)
        if (!isImage) {
          // đưa con trỏ ra khỏi liên kết để gõ tiếp không bị dính vào tên tệp
          chain = chain.unsetMark('link').insertContent(' ')
        }
        chain.run()
      }
      this.$emit('attached', file)
    },
    onFailure() {
      this.$toast({
        title: 'Không tải được tệp lên',
        icon: 'x',
        iconClasses: 'text-ink-red-4',
      })
    },
  },
}
</script>
