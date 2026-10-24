<template>
  <FormControl
    label="Tên nhóm"
    placeholder="Ra mắt sản phẩm"
    @update:modelValue="(project) => $emit('update:modelValue', { ...modelValue, project })"
    v-model="modelValue.project"
  />
</template>
<script>
export default {
  name: 'OnboardingStepProject',
  props: ['modelValue'],
  emits: ['update:modelValue'],
}
</script>
