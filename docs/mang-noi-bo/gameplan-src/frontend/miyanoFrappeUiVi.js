// Miyano: Việt hóa các chuỗi hiển thị bên trong thư viện frappe-ui lúc build (không sửa node_modules).
const editorLabels = {
  Paragraph: 'Đoạn văn',
  'Heading 1': 'Tiêu đề 1',
  'Heading 2': 'Tiêu đề 2',
  'Heading 3': 'Tiêu đề 3',
  'Heading 4': 'Tiêu đề 4',
  'Heading 5': 'Tiêu đề 5',
  'Heading 6': 'Tiêu đề 6',
  Bold: 'In đậm',
  Italic: 'In nghiêng',
  Underline: 'Gạch chân',
  'Bullet List': 'Danh sách dấu chấm',
  'Numbered List': 'Danh sách đánh số',
  'Align Center': 'Căn giữa',
  'Align Left': 'Căn trái',
  'Align Right': 'Căn phải',
  'Font Color': 'Màu chữ',
  Blockquote: 'Trích dẫn',
  Code: 'Mã',
  'Horizontal Rule': 'Đường kẻ ngang',
  Link: 'Liên kết',
  Image: 'Chèn ảnh',
  Video: 'Chèn video',
  Undo: 'Hoàn tác',
  Redo: 'Làm lại',
  'Insert Table': 'Chèn bảng',
  'Add Column Before': 'Thêm cột bên trái',
  'Add Column After': 'Thêm cột bên phải',
  'Delete Column': 'Xóa cột',
  'Add Row Before': 'Thêm hàng phía trên',
  'Add Row After': 'Thêm hàng phía dưới',
  'Delete Row': 'Xóa hàng',
  'Delete Table': 'Xóa bảng',
  'Merge Cells': 'Gộp ô',
  'Split Cell': 'Tách ô',
  'Toggle Header Column': 'Bật/tắt cột tiêu đề',
  'Toggle Header Row': 'Bật/tắt hàng tiêu đề',
  'Toggle Header Cell': 'Bật/tắt ô tiêu đề',
}

const fileReplacements = {
  'components/TextEditor/commands.js': Object.entries(editorLabels).map(([en, vi]) => [
    `label: '${en}'`,
    `label: '${vi}'`,
  ]),
  'components/TextEditor/InsertLink.vue': [
    ["title: 'Set Link'", "title: 'Gắn liên kết'"],
    ['label="URL"', 'label="Địa chỉ (URL)"'],
    ['\n        Save\n', '\n        Lưu\n'],
  ],
  'components/TextEditor/InsertImage.vue': [
    ["title: 'Add Image'", "title: 'Chèn ảnh'"],
    ["'Select another image'", "'Chọn ảnh khác'"],
    ["'Select an image'", "'Chọn ảnh từ máy'"],
    ['Insert Image', 'Chèn ảnh'],
    ['> Cancel <', '> Hủy <'],
  ],
  'components/TextEditor/InsertVideo.vue': [
    ["title: 'Add Video'", "title: 'Chèn video'"],
    ['`Uploading ${progress}%`', '`Đang tải lên ${progress}%`'],
    ["'Change Video'", "'Đổi video'"],
    ["'Upload Video'", "'Tải video lên'"],
    ['Remove', 'Gỡ bỏ'],
    ['Insert Video', 'Chèn video'],
    ['>Cancel<', '>Hủy<'],
  ],
  'components/TextEditor/FontColor.vue': [
    ['>Text Color<', '>Màu chữ<'],
    ['>Background Color<', '>Màu nền<'],
  ],
  'components/Autocomplete.vue': [
    ['placeholder="Search"', 'placeholder="Tìm kiếm"'],
    ['No results found', 'Không tìm thấy kết quả'],
    ['label="Select All"', 'label="Chọn tất cả"'],
    ['label="Clear All"', 'label="Bỏ chọn tất cả"'],
  ],
}

export default function miyanoFrappeUiVi() {
  return {
    name: 'miyano-frappe-ui-vi',
    enforce: 'pre',
    transform(code, id) {
      if (id.includes('?')) return null
      let path = id.replace(/\\/g, '/')
      let marker = '/frappe-ui/src/'
      let i = path.lastIndexOf(marker)
      if (i === -1) return null
      let rel = path.slice(i + marker.length)
      let pairs = fileReplacements[rel]
      if (!pairs) return null
      for (let [from, to] of pairs) {
        if (!code.includes(from)) {
          this.warn(`[miyano-vi] không thấy chuỗi "${from}" trong frappe-ui/${rel}`)
          continue
        }
        code = code.split(from).join(to)
      }
      return { code, map: null }
    },
  }
}
