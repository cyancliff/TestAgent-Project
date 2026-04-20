import { marked } from 'marked'

const ALLOWED_MARKDOWN_TAGS = new Set([
  'a',
  'blockquote',
  'br',
  'code',
  'del',
  'em',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'hr',
  'li',
  'ol',
  'p',
  'pre',
  'strong',
  'table',
  'tbody',
  'td',
  'th',
  'thead',
  'tr',
  'ul',
])

const BLOCKED_MARKDOWN_TAGS = new Set([
  'button',
  'embed',
  'form',
  'iframe',
  'input',
  'object',
  'script',
  'select',
  'style',
  'textarea',
])

const SAFE_LINK_PATTERN = /^(https?:|mailto:|tel:|\/|#)/i

export const sanitizeRenderedMarkdown = (html) => {
  if (!html) return ''

  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const nodes = [...doc.body.querySelectorAll('*')]

  for (const node of nodes) {
    const tag = node.tagName.toLowerCase()

    if (BLOCKED_MARKDOWN_TAGS.has(tag)) {
      node.remove()
      continue
    }

    if (!ALLOWED_MARKDOWN_TAGS.has(tag)) {
      node.replaceWith(...Array.from(node.childNodes))
      continue
    }

    for (const attr of [...node.attributes]) {
      const name = attr.name.toLowerCase()
      const value = attr.value.trim()

      if (tag === 'a' && name === 'href') {
        if (SAFE_LINK_PATTERN.test(value)) {
          node.setAttribute('target', '_blank')
          node.setAttribute('rel', 'noopener noreferrer')
        } else {
          node.removeAttribute(attr.name)
        }
        continue
      }

      if (tag === 'a' && (name === 'rel' || name === 'target' || name === 'title')) {
        continue
      }

      node.removeAttribute(attr.name)
    }
  }

  return doc.body.innerHTML
}

export const cleanReportText = (raw) => {
  if (!raw) return ''

  return String(raw)
    .replace(/【内部记录[：:][\s\S]*?】/g, '')
    .replace(/\s*TERMINATE\s*/g, '')
    .replace(/##\s*知识库引用[\s\S]*?(?=\n##\s|\s*$)/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export const renderSafeMarkdown = (text) => {
  if (!text) return ''
  return sanitizeRenderedMarkdown(marked.parse(String(text), { breaks: true, gfm: true }))
}

export const renderReportMarkdown = (text) => renderSafeMarkdown(cleanReportText(text))
