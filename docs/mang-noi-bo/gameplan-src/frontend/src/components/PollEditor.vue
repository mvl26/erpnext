<template>
  <div class="space-y-4">
    <FormControl
      type="text"
      label="Câu hỏi"
      v-model="poll.title"
      @change="$emit('update:poll', poll)"
      autocomplete="off"
    />
    <div class="space-y-2">
      <div class="text-sm leading-4 text-ink-gray-7">Lựa chọn</div>
      <TextInput
        v-for="option in poll.options"
        :key="option.idx"
        :placeholder="`Lựa chọn ${option.idx}`"
        v-model="option.title"
        @update:modelValue="(val) => onOptionChange(option, val)"
      />
    </div>
    <FormControl
      type="checkbox"
      label="Ẩn danh"
      v-model="poll.anonymous"
      @change="$emit('update:poll', poll)"
    />
    <div class="flex justify-end space-x-2">
      <Button v-bind="discardButtonProps">Bỏ</Button>
      <Button v-bind="submitButtonProps" variant="solid">Gửi</Button>
    </div>
  </div>
</template>
<script>
import { debounce } from 'frappe-ui'

export default {
  name: 'PollEditor',
  props: ['poll', 'submitButtonProps', 'discardButtonProps'],
  events: ['update:poll'],
  methods: {
    onOptionChange: debounce(function (option, value) {
      option.title = value
      let lastOption =
        this.poll.options.length > 0 && this.poll.options[this.poll.options.length - 1]
      if (lastOption?.title) {
        this.poll.options.push({
          title: '',
          idx: lastOption.idx + 1,
        })
      }
      this.$emit('update:poll', this.poll)
    }, 100),
  },
}
</script>
