import type { ReactNode } from 'react'

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index))
    }

    const token = match[0]
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={`${match.index}-strong`}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(<em key={`${match.index}-em`}>{token.slice(1, -1)}</em>)
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      if (linkMatch) {
        parts.push(
          <a key={`${match.index}-link`} href={escapeHtml(linkMatch[2])} target="_blank" rel="noreferrer">
            {linkMatch[1]}
          </a>,
        )
      }
    }

    lastIndex = match.index + token.length
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex))
  }

  return parts
}

export default function SimpleMarkdown({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/).filter(Boolean)

  return (
    <>
      {blocks.map((block, index) => {
        const lines = block.split('\n').filter(Boolean)
        const isList = lines.every(line => /^[-*]\s+/.test(line))

        if (isList) {
          return (
            <ul key={`block-${index}`}>
              {lines.map((line, lineIndex) => (
                <li key={`line-${lineIndex}`}>{renderInline(line.replace(/^[-*]\s+/, ''))}</li>
              ))}
            </ul>
          )
        }

        return (
          <p key={`block-${index}`}>
            {lines.map((line, lineIndex) => (
              <span key={`line-${lineIndex}`}>
                {lineIndex > 0 ? <br /> : null}
                {renderInline(line)}
              </span>
            ))}
          </p>
        )
      })}
    </>
  )
}
