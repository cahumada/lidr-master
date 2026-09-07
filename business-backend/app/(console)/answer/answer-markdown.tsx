"use client"

import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"

/**
 * The assistant's answer, rendered as markdown.
 *
 * The synthesis prompt asks the model to STRUCTURE its answer — a continuous
 * explanation, Función and Efecto kept apart, and a closing `Fuentes citadas:`
 * list in an exact format. Showing that as plain text threw the structure
 * away and put the asterisks on screen.
 *
 * No raw HTML: `react-markdown` ignores embedded markup unless `rehype-raw`
 * is added, and it is not added. The text comes from a model writing over
 * corpus content, and allowing arbitrary markup from a source nobody reviews
 * is a security decision, not a styling one.
 *
 * The component map is explicit rather than `@tailwindcss/typography`: the
 * plugin brings a whole type scale to style five elements, and its reset
 * fights the shadcn tokens the rest of the console already uses.
 *
 * || La respuesta del asistente, renderizada como markdown. El prompt de
 * síntesis le pide al modelo que ESTRUCTURE y la consola mostraba eso como
 * texto plano, con los asteriscos a la vista. Sin HTML crudo: el texto lo
 * escribe un modelo sobre contenido de corpus, y habilitar markup arbitrario
 * desde una fuente que nadie revisa es una decisión de seguridad. El mapa de
 * componentes es explícito y no `@tailwindcss/typography`, cuyo reset pelea
 * con los tokens de shadcn que ya usa el resto de la consola.
 */
export function AnswerMarkdown({ children }: { children: string }) {
  return (
    <div className="text-sm leading-relaxed [&>*+*]:mt-3">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          // A contained scale on purpose: the model does not know the
          // console's visual hierarchy, and an `h1` it writes must not
          // outweigh the screen's own title.
          // || Escala contenida a propósito: el modelo no conoce la jerarquía
          // visual de la consola, y un `h1` suyo no puede pesar más que el
          // título de la pantalla.
          h1: ({ children }) => (
            <h3 className="mt-4 text-sm font-semibold">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="mt-4 text-sm font-semibold">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="mt-4 text-sm font-semibold">{children}</h4>
          ),
          h4: ({ children }) => (
            <h5 className="text-muted-foreground mt-3 text-xs font-semibold uppercase">
              {children}
            </h5>
          ),
          code: ({ children }) => (
            <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs">
              {children}
            </code>
          ),
          // Its own scroll container: a wide block cannot widen the turn
          // bubble or the page. || Contenedor propio: un bloque ancho no
          // puede ensanchar la burbuja del turno ni la página.
          pre: ({ children }) => (
            <pre className="bg-muted overflow-x-auto rounded-lg p-3 font-mono text-xs">
              {children}
            </pre>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="text-muted-foreground border-l-2 pl-3 italic">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="border-border" />,
          table: ({ children }) => (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-muted/50 text-left">{children}</thead>
          ),
          th: ({ children }) => (
            <th className="border-b px-3 py-2 font-medium">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border-b px-3 py-2 align-top">{children}</td>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
  )
}
