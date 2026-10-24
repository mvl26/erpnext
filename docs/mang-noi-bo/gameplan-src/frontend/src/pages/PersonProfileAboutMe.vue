<template>
  <div class="mt-7 pb-16">
    <h2 class="mb-3 text-lg font-semibold text-ink-gray-9">Giới thiệu</h2>
    <ReadmeEditor
      :resource="profile"
      :editable="$isSessionUser(profile.doc.user)"
      fieldname="readme"
      :placeholder="
        $isSessionUser(profile.doc.user)
          ? 'Viết vài dòng giới thiệu về bản thân...'
          : 'Chưa có giới thiệu'
      "
      :border="false"
    />
  </div>
</template>
<script>
import ReadmeEditor from '@/components/ReadmeEditor.vue'
export default {
  name: 'PersonProfileAboutMe',
  props: ['profile'],
  components: { ReadmeEditor },
}
</script>
