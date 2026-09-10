# Estándares de frontend

Convenciones de la consola en `business-backend/`: páginas App Router,
componentes, tema y navegación. Los Route Handlers y `lib/ai-service/`
son servidor — [bff-standards.md](./bff-standards.md).

## Stack

| Capa | Tecnología |
|---|---|
| Framework | Next.js 16 App Router, React 19 |
| Lenguaje | TypeScript 5, `strict` |
| Estilos | Tailwind CSS v4 |
| Componentes | shadcn/ui copiados a `components/ui/` (no una lib en `node_modules`) |
| Iconos | Lucide React |
| Markdown | `react-markdown` + `remark-gfm` (respuesta del chat) |
| Tema | Tokens del tema Woken (tweakcn) en `app/globals.css`; mecánica en `lib/theme.ts` |
| Datos | Server Components + Route Handlers. El browser **no** habla con el servicio IA |
| Tests | `pnpm test` cubre `lib/auth/` (`node --test` + `tsx`). **De UI no hay runner**; CI corre `pnpm lint`, `pnpm test` y `pnpm build` |

No hay client-side router aparte del App Router, no hay cliente HTTP
de terceros, no hay librería de tema ni de i18n. No introducirlos sin
proposal.

**Auth sí hay**, desde `add-console-authentication`: Auth.js v5 con Google
y contraseña, sesión en JWT. Lo que hay que saber desde el frontend son dos
cosas y las dos son límites, no APIs nuevas:

- **Ninguna pantalla decide si se puede entrar.** El rol se resuelve en el
  servidor —`app/(console)/layout.tsx` para la sesión,
  `app/(console)/(admin)/layout.tsx` para el rol— y una pantalla que ya
  renderiza es una pantalla que pasó el gate. No repetir el chequeo en un
  Client Component: no agrega seguridad y crea una segunda fuente de verdad.
- **El filtro de la nav es presentación.** `visibleModules(role)` oculta lo
  que no se puede abrir; no autoriza. La mecánica completa está en
  [bff-standards.md](./bff-standards.md) §Identidad.

Comandos, desde `business-backend/`:

```bash
pnpm dev
pnpm lint
pnpm test
pnpm build
```

## Estructura

No es feature-based. Es una consola chica organizada por ruta, con
shell compartido y una sola capa de datos:

```
business-backend/
├── app/
│   ├── layout.tsx              # solo el shell del documento: <html>, tema
│   ├── (auth)/                 # antes de la sesión: sin sidebar ni header
│   │   ├── login/
│   │   └── register/           # + register/pending
│   ├── (console)/              # detrás de la sesión: shell + gate
│   │   ├── layout.tsx          # sidebar + header; resuelve la sesión
│   │   ├── page.tsx            # portada
│   │   ├── answer/             # chat (page + console + markdown)
│   │   ├── search/
│   │   ├── documents/
│   │   └── (admin)/            # el grupo es el gate de rol
│   │       ├── layout.tsx      # exige `administrador`
│   │       ├── corpus/
│   │       ├── agents/         # catálogo + /flow
│   │       ├── models/
│   │       ├── usage/
│   │       └── users/
│   └── api/                    # BFF — no es frontend
├── components/
│   ├── ui/                     # shadcn: solo los que se usan
│   ├── page-frame.tsx
│   ├── app-sidebar.tsx
│   ├── app-header.tsx
│   ├── forbidden-screen.tsx    # el 403 con pantalla propia
│   └── theme-toggle.tsx
├── lib/
│   ├── ai-service/             # server-only; ver bff-standards
│   ├── auth/                   # identidad; ver bff-standards §Identidad
│   ├── theme.ts
│   ├── console-nav.ts          # única fuente de la nav
│   └── utils.ts                # cn()
└── hooks/
    └── use-mobile.ts
```

Los grupos de ruta —`(auth)`, `(console)`, `(admin)`— no aparecen en la URL:
`app/(console)/(admin)/models/page.tsx` sirve `/models`. Están para que cada
grupo tenga su layout, y en el caso de `(admin)` eso **es** la autorización:
una pantalla está protegida porque está en ese directorio. Mover una carpeta
adentro o afuera del grupo cambia quién la puede abrir.

- Una pantalla nueva es una carpeta con `page.tsx` (Server Component) y el
  cliente interactivo al lado (`*-console.tsx`). **En qué grupo va es parte
  del change**: `(console)/` si cualquier sesión puede abrirla,
  `(console)/(admin)/` si escribe configuración o destruye datos. Dejarla
  fuera de `(console)/` la publica sin sesión.
- El ítem de nav se agrega en `CONSOLE_MODULES` (`lib/console-nav.ts`)
  en el mismo change. Sidebar y portada leen de ahí: una pantalla que
  está en uno y no en el otro es un bug.
- shadcn se copia **solo cuando se usa**. Un `components/ui/` de
  cuarenta archivos para seis en uso es pre-construir capas vacías.
- `api/` no se importa desde un Client Component para hablar con el
  servicio IA. El Server Component llama a `lib/ai-service/*`; el
  cliente llama a `/api/...` (same-origin).

## Idioma y nombres

Igual que [base-standards.md](./base-standards.md):

- Componentes y tipos en PascalCase (`SearchConsole`, `ServiceConfig`).
- Funciones, hooks y variables en camelCase (`serviceConfig`,
  `useMobile`).
- Archivos de componente en kebab o el nombre de la ruta
  (`answer-console.tsx`, `page-frame.tsx`). No mezclar
  `SearchConsole.tsx` y `answer-console.tsx` en el mismo change sin
  motivo: seguir el vecino de la carpeta.
- Hooks con prefijo `use`.
- Texto de UI en español. Comentarios bilingües `EN || ES`.
- Logs de consola en inglés si hacen falta; preferir no loguear.

```typescript
// Good
type SearchConsoleProps = {
  initialFacets: SearchFacets
}

export function SearchConsole({ initialFacets }: SearchConsoleProps) {
  const [query, setQuery] = useState("")
  // ...
}

// Avoid
export const ConsolaBusqueda = ({ facetasIniciales }: Props) => { ... }
```

## Componentes

- Funcionales, con hooks. No class components.
- Props tipadas, desestructuradas. Nada de `React.FC` salvo que el
  vecino del archivo ya lo use.
- `"use client"` solo donde hay estado, efectos o event handlers. La
  página (`page.tsx`) es Server Component: fetch inicial, metadata,
  degradación si el servicio no responde.
- El chat es la excepción de layout: no usa `PageFrame` porque el
  hilo necesita el inset entero. El resto de pantallas-herramienta
  usan `PageFrame` + `PageIntro`.

```typescript
// app/search/page.tsx — servidor
export default async function SearchPage() {
  const initialFacets = await facets().catch(() => ({ modules: [], window_types: [] }))
  return (
    <PageFrame>
      <PageIntro title="Búsqueda">…</PageIntro>
      <SearchConsole initialFacets={initialFacets} />
    </PageFrame>
  )
}
```

Una falla del servicio **no** tumba la página. Facets, config y
jobs degradan a vacío / `null` + mensaje. “No pude hablar con el
servicio” es más útil que un error page.

## Estado y datos

- Estado de UI (`useState`) en el console client: query, knobs,
  resultado, error, loading.
- Datos iniciales en el Server Component. El primer pintado ya tiene
  opciones reales, no un spinner de combos.
- El cliente habla con `/api/...`, nunca con el host del servicio.
- No hay axios. `fetch` same-origin, `cache: "no-store"` implícito
  en los handlers.
- No hay store global ni React Query. Cuando un dato se comparte
  (catálogo de agentes), se vuelve a pedir: es barato y no se
  desincroniza. Extraer un hook solo si dos consolas copian el mismo
  fetch + mapping.

Loading y error:

- `Skeleton` de `components/ui/skeleton` cuando el contenido tiene
  forma (tabla, cards).
- `Alert` / `AlertDescription` para un error que tiene que quedarse
  en la página.
- Texto de error: el `error` que devolvió el BFF (`toErrorPayload`),
  no el stack ni el JSON crudo.
- Botón de submit / rebuild deshabilitado mientras corre (`aria-busy`).

No hay toasts (Sonner no está instalado). No agregarlo para un
“Guardado” si un `Alert` o el propio estado de la pantalla ya lo
dice. Si entra, es un change que justifica la dependencia.

## Tema

Claro y oscuro son de primera. La mecánica vive en `lib/theme.ts` y
en un script inline en `<head>` — **antes** del primer pintado.

- Tokens en `app/globals.css` (`:root` y `.dark`). Salen literales
  del registry item Woken. Cambiar de tema es reemplazar esos
  bloques; un hex retocado a mano se pierde en la próxima
  regeneración.
- Ninguna pantalla fija un color que no salga de esos tokens
  (`bg-background`, `text-muted-foreground`, `border-border`, …).
- Sin elección del usuario: `prefers-color-scheme`. Con elección:
  `localStorage` clave `theme`. La elección le gana al sistema y
  sobrevive la recarga.
- El servidor no puede saber el tema. Por eso el script corre en
  `<head>` y `<html>` **no** lleva `className` en JSX: React
  resetearía `dark` al hidratar. `suppressHydrationWarning` está
  puesto a propósito.
- El conmutador está en el header (`theme-toggle.tsx`). No montar
  un segundo.

```typescript
// Avoid
<div className="bg-white text-black">   // rompe el oscuro
<div className="bg-[#0a0a0a]">          // token retocado a mano
```

## shadcn / Tailwind

- Instalar un componente con la CLI de shadcn y dejarlo en
  `components/ui/`. Editar el archivo copiado, no wrappear una lib.
- `cn()` de `lib/utils.ts` para componer clases.
- Breakpoints de Tailwind (`sm`, `md`, `lg`). El sidebar ya colapsa
  con `use-mobile`; no reinventar un drawer.
- `PageFrame` limita a `max-w-6xl`. No crear un segundo container
  con otros márgenes “porque esta pantalla es especial” — el chat
  ya es esa excepción, y está documentada.

## Formularios y acciones

- Inputs y botones de shadcn (`Input`, `Textarea`, `Button`,
  `Select`, `Switch`).
- Acciones primarias a la derecha del bloque (`justify-end`).
- Icono de Lucide junto al label en acciones de toolbar cuando el
  vecino de la pantalla ya lo hace. No inventar un `ActionButton`
  compartido hasta que tres pantallas copien el mismo patrón.
- Confirmación destructiva (reset del corpus, borrar perfil): el
  servicio pide confirmación (`confirm_tenant_id` /
  `confirm_doc_version`). La UI no puede “saltársela” con un POST
  sin esos campos.

## Navegación

- `CONSOLE_MODULES` es la fuente. Tres módulos: Respuesta, RAG,
  Configuración.
- Links con `next/link`. Títulos y descripciones en español, en
  el objeto de nav — no hardcodeados otra vez en la portada.
- Metadata por página (`title: "Búsqueda · Visual Time RAG"`).
- Inventario: [app-routes.md](./app-routes.md). No borrar una
  `page.tsx` de esa lista.

## Accesibilidad

- Controles con label visible o `aria-label`.
- El conmutador de tema y los iconos-solo llevan texto accesible.
- Contraste: los tokens del tema ya están pensados para claro y
  oscuro; no poner `text-muted-foreground` sobre
  `bg-muted` si el bloque queda ilegible — verificar los dos temas.
- `lang="es"` en `<html>`.
- Skeletons / áreas que cargan: `aria-busy="true"` cuando aplica.
- El markdown de la respuesta se renderiza como HTML: no inyectar
  HTML crudo del modelo. `react-markdown` es el camino.

## Performance

- Fetch en el Server Component para el primer pintado.
- Client Components chicos: el console, no la página entera.
- No importar `lib/ai-service` en un cliente (rompe el build).
- No bajar una webfont: Woken usa stacks del sistema
  (`--font-sans`, `--font-mono`). `next/font` encima descargaría
  bytes que nadie pinta.
- Listas y jobs: pedir lo que la pantalla muestra (p. ej. 20 jobs
  recientes), no el histórico entero.

## Workflow de este stack

- Rama con sufijo `-web`. Ver [git-workflow.md](./git-workflow.md).
- `pnpm lint`, `pnpm test` y `pnpm build` en verde.
- Verificar en el browser el flujo que se tocó — no solo un
  screenshot. Si no hay browser tools, `pnpm build` + decir qué no
  se pudo clickear.
- Toda ruta o ítem de nav nuevo se agrega a `CONSOLE_MODULES` y a
  [app-routes.md](./app-routes.md) en el mismo change.
- Dependencia nueva (un componente shadcn no cuenta: es un archivo
  copiado): justificarla en el proposal. El SDK de streaming de
  Vercel no entra hasta que haya streaming, y entra apuntado al
  Route Handler propio, nunca a un vendor.

## Despliegue (Vercel)

Páginas y BFF son **un** proyecto Next y se despliegan juntos en
**Vercel** (root `business-backend/`). El servicio IA no vive acá:
está en Railway. El browser solo ve el origen de Vercel; las
llamadas al servicio salen de los Route Handlers. Detalle de
variables, `ignoreCommand` y timeouts:
[bff-standards.md](./bff-standards.md#despliegue-vercel).
