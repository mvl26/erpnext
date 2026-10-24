<template>
  <Dialog :options="{ title: 'Thêm không gian' }" v-model="showDialog">
    <template #body-content>
      <div class="space-y-4">
        <FormControl
          label="Tên không gian"
          type="text"
          v-model="newTeam.title"
          placeholder="Tên không gian"
          @keydown.enter="createTeam($event.target.value)"
          autocomplete="off"
        />
        <FormControl
          type="select"
          label="Chế độ hiển thị"
          :options="[
            { label: 'Mọi người đều thấy', value: 0 },
            { label: 'Chỉ thành viên không gian thấy (Riêng tư)', value: 1 },
          ]"
          v-model="newTeam.is_private"
        />
        <ErrorMessage :message="teams.insert.error?.messages" />
      </div>
    </template>
    <template #actions>
      <Button
        variant="solid"
        class="w-full"
        @click="createTeam(teamName)"
        :loading="teams.insert.loading"
      >
        Tạo không gian
      </Button>
    </template>
  </Dialog>
</template>
<script>
import { teams } from '@/data/teams'

export default {
  name: 'AddTeamDialog',
  props: ['show'],
  emits: ['success', 'update:show'],
  data() {
    return {
      newTeam: { title: '', is_private: 0 },
      teams,
    }
  },
  methods: {
    createTeam() {
      teams.insert.submit(this.newTeam, {
        onSuccess: (team) => {
          this.$resetData('newTeam')
          this.showDialog = false
          this.$emit('success', team)
        },
      })
    },
  },
  computed: {
    showDialog: {
      get() {
        return this.show
      },
      set(val) {
        this.$emit('update:show', val)
      },
    },
  },
}
</script>
