import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import './RichTextEditor.css'

export default function RichTextEditor({ content, onChange }) {
  const editor = useEditor({
    extensions: [StarterKit, Underline],
    content,
    onUpdate({ editor }) {
      onChange(editor.getHTML())
    },
  })

  if (!editor) return null

  function btn(label, isActive, action, title) {
    return (
      <button
        type="button"
        title={title}
        className={`rte-btn${isActive ? ' is-active' : ''}`}
        onMouseDown={e => { e.preventDefault(); action() }}
      >{label}</button>
    )
  }

  return (
    <div className="rte-wrapper">
      <div className="rte-toolbar">
        {btn(<strong>B</strong>, editor.isActive('bold'),
          () => editor.chain().focus().toggleBold().run(), 'Bold')}
        {btn(<em>I</em>, editor.isActive('italic'),
          () => editor.chain().focus().toggleItalic().run(), 'Italic')}
        {btn(<u>U</u>, editor.isActive('underline'),
          () => editor.chain().focus().toggleUnderline().run(), 'Underline')}
        <div className="rte-divider" />
        {btn(
          <svg width="15" height="15" viewBox="0 0 15 15" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="2" cy="3.5" r="1.2" fill="currentColor"/>
            <circle cx="2" cy="7.5" r="1.2" fill="currentColor"/>
            <circle cx="2" cy="11.5" r="1.2" fill="currentColor"/>
            <line x1="5" y1="3.5" x2="14" y2="3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="5" y1="7.5" x2="14" y2="7.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="5" y1="11.5" x2="14" y2="11.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>,
          editor.isActive('bulletList'),
          () => editor.chain().focus().toggleBulletList().run(), 'Bullet list')}
        {btn(
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="10" y1="6"  x2="21" y2="6"/>
            <line x1="10" y1="12" x2="21" y2="12"/>
            <line x1="10" y1="18" x2="21" y2="18"/>
            <path d="M4 6h1v4"/>
            <path d="M4 10h2"/>
            <path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1"/>
          </svg>,
          editor.isActive('orderedList'),
          () => editor.chain().focus().toggleOrderedList().run(), 'Numbered list')}
      </div>
      <EditorContent editor={editor} className="rte-content" />
    </div>
  )
}
