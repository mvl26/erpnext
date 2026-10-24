<template>
  <FileUploader @success="(file) => setUserImage(file.file_url)" :validateFile="validateFile">
    <template v-slot="{ file, progress, error, uploading, openFileSelector }">
      <div class="flex flex-col items-center">
        <button class="group relative rounded-full border-2" @click="openFileSelector">
          <div
            class="absolute inset-0 grid place-items-center rounded-full bg-gray-400/20 text-base text-ink-gray-5 transition-opacity"
            :class="[
              uploading ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
              'drop-shadow-sm',
            ]"
          >
            <span class="inline-block rounded-md bg-surface-gray-7/60 px-2 py-1 text-ink-white">
              {{
                uploading
                  ? `Đang tải lên ${progress}%`
                  : profile.doc.image
                    ? 'Đổi ảnh'
                    : 'Tải ảnh lên'
              }}
            </span>
          </div>
          <img
            v-if="profile.doc.image"
            class="h-64 w-64 rounded-full object-cover"
            :src="profile.doc.image"
            alt="Ảnh hồ sơ"
            :style="{
              backgroundColor: profile.doc.image_background_color || null,
            }"
          />
          <div v-else class="h-64 w-64 rounded-full bg-surface-gray-2"></div>
        </button>
        <ErrorMessage class="mt-4" :message="profile.removeImageBackground.error || error" />
        <div class="mt-4 flex items-center gap-4">
          <Button
            v-if="profile.doc.image && profile.doc.original_image && isBackgroundRemovalAvailable"
            @click="profile.revertImageBackground.submit()"
            :loading="profile.revertImageBackground.loading"
          >
            Khôi phục ảnh gốc
          </Button>
          <Button
            v-if="profile.doc.image && !profile.doc.original_image && isBackgroundRemovalAvailable"
            @click="
              profile.removeImageBackground.submit({
                default_color: getRandomColor(),
              })
            "
            :loading="profile.removeImageBackground.loading"
          >
            Đặt nền màu
          </Button>
          <ColorPicker
            v-if="profile.doc.is_image_background_removed && isBackgroundRemovalAvailable"
            v-model="profile.doc.image_background_color"
            @update:modelValue="
              profile.setValue.submit({
                image_background_color: profile.doc.image_background_color,
              })
            "
          >
            <template v-slot="{ isOpen }">
              <Button> Đổi màu nền </Button>
            </template>
          </ColorPicker>

          <Button v-if="profile.doc.image" @click="setUserImage(null)"> Gỡ ảnh </Button>
        </div>
      </div>
    </template>
  </FileUploader>
</template>
<script>
import { FileUploader } from 'frappe-ui'
import ColorPicker, { getRandomColor } from './ColorPicker.vue'

export default {
  name: 'ProfileImageEditor',
  props: ['profile'],
  components: { FileUploader, ColorPicker },
  data() {
    return {
      isBackgroundRemovalAvailable: false,
    }
  },
  mounted() {
    this.profile.isBackgroundRemovalAvailable.submit().then((result) => {
      this.isBackgroundRemovalAvailable = result
    })
  },
  methods: {
    setUserImage(url) {
      this.profile.setImage.submit({ image: url })
    },
    getRandomColor,
    validateFile(file) {
      let extn = file.name.split('.').pop().toLowerCase()
      if (!['png', 'jpg'].includes(extn)) {
        return 'Chỉ chấp nhận ảnh PNG và JPG'
      }
    },
  },
}
</script>
