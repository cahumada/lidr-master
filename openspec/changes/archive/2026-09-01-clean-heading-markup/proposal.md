## Why

El header contextual (`[Documento: X - Título]\n[Sección: S > bullet_path]`)
existe para que un chunk suelto se entienda cuando lo recupera una búsqueda. Se
embebe y se hashea junto al cuerpo. Hoy arrastra el marcado del export de Word:

```
[Sección: Proceso** Batch > > ### ******Proceso]
[Sección: Información********Técnica]
[Sección: [Campos](../../seguridad/valschemaoffice.html)]
```

**5.551 chunks (8,92%)** llevan ruido de marcado en su header
[VERIFICADO-CORPUS]. No es solo feo: cuesta tokens en el vector y ensucia el
único campo que la capa de recuperación va a usar para filtrar por sección.

De los cuales **2.656 (4,27%, 83 documentos)** lo llevan en `metadata.section`,
que es campo filtrable. La misma sección aparece escrita de tres formas
distintas y ninguna agrupa con las demás:

| `metadata.section` | chunks |
|---|---:|
| `Proceso****Batch` | 756 |
| `Proceso** Batch` | 635 |
| `Proceso********Batch` | 478 |

Las tres deberían ser `Proceso batch`, que es como está escrito en los otros
2.100 documentos.

## El defecto de fondo: un `\s` que cruza saltos de línea

`H2_PATTERN`, `H1_PATTERN` y `TITLE_PATTERN` son `^#{1,2}\s+(.+?)\s*$` con
`re.MULTILINE`. `MULTILINE` cambia dónde anclan `^` y `$`, pero **no** impide
que `\s+` consuma un `\n`. Un heading vacío se come la línea siguiente:

```
##                          <- el export emite un H2 sin texto
                            <- \s+ se traga los dos saltos
## Notas al programador     <- y esto queda como NOMBRE de la sección
```

Consecuencias, medidas contra los 2.169 archivos fuente [VERIFICADO-CORPUS]:

- **62 archivos** con un heading tragado.
- **68 secciones fantasma**: un `##` vacío seguido de prosa crea una sección
  cuyo nombre es un párrafo del cuerpo.
- **2 documentos** (`CPL011`, `CPL018`) cuyo título literalmente empieza con
  `# `.

Esto no es cosmético: cuando el heading real es tragado, su contenido queda
atribuido a una sección que no existe con ese nombre.

## What Changes

- **Los patrones de heading dejan de cruzar líneas.** `\s` → `[ \t]` en
  `TITLE_PATTERN`, `H1_PATTERN` y `H2_PATTERN`.
- **Una función `heading_text()`** que devuelve el nombre humano de un heading,
  reemplazando a `_strip_emphasis` en los puntos donde hoy se usa para nombrar
  algo. Quita, en este orden: el glifo de viñeta de Word que abre la línea, los
  marcadores `#`, la sintaxis de link (conservando la etiqueta), el énfasis, y
  los escapes del export (`\(` → `(`).
- **Un `*` interior se colapsa a un espacio; un `_` interior NO.** Es la regla
  de CommonMark, no un criterio inventado: `foo_bar` no lleva énfasis, `a*b*c`
  sí. En el corpus hay `Conteo de unidades por unit_type`, donde tratar el `_`
  como énfasis rompería el identificador.

## Capabilities

### Capability modificada

- `document-chunking`: qué es el nombre de una sección y qué lleva el header
  contextual.

## Impact

- `app/generation/rag/chunking/functional_spec.py` — los tres patrones y
  `heading_text()`.
- `openspec/specs/document-chunking/spec.md`.
- Cambian `metadata.section`, `bullet_path` y el `text` de los chunks
  afectados, así que cambia su `content_hash`. La reingesta incremental
  re-embebe solo esos: el diseño de `chunk-embedding` ya lo cubre.
- Algunos `chunk_id` cambian, los de secciones que hoy son un link
  (`campos_ma5571_html` → `campos`). El slug de los casos de énfasis **no**
  cambia, porque `_slugify` ya colapsa los no-alfanuméricos.

## Lo que este cambio NO hace

- **No toca los glifos de viñeta en el cuerpo.** Eso es
  `fix-dangling-lead-in-chunks`, ya archivado; acá solo se limpia la etiqueta.
- **No fusiona secciones homónimas.** Que `Proceso batch` aparezca ahora escrito
  igual en todos lados es el requisito para poder agrupar; agrupar es de la capa
  de recuperación.
- **No arregla los H2 que el export usó como viñeta** (`## o _Ramo
  \(parámetro\)._`, 267 headings). Se les limpia el nombre; que sean secciones
  de una línea es otra discusión.
