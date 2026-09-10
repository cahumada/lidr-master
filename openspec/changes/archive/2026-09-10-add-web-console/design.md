## El límite que el curso defiende, traducido a Vercel + Railway

El `docker-compose.yml` del curso tiene una propiedad deliberada:
**`business-backend` es el único servicio con puertos publicados**. El servicio
IA y las dos bases son internas, alcanzables solo por la red de compose. Es la
propiedad de seguridad sobre la que gira su sesión de despliegue.

Esa topología no se puede copiar: Vercel y Railway son dos plataformas
distintas, así que el servicio IA necesita una URL pública para que la app web
lo alcance. Lo que sí se puede conservar es **la propiedad**, y para eso sirve
que todas las llamadas salgan del servidor de Next.js:

| | curso (compose) | acá (Vercel + Railway) |
|---|---|---|
| lo que el browser puede alcanzar | solo `business-backend:3000` | solo el origen de Vercel |
| dónde vive la URL del servicio IA | DNS interno de compose | `AI_SERVICE_URL`, variable privada del servidor |
| qué pasa si el browser la adivina | no hay ruta hasta ahí | la alcanza — por eso nunca se le entrega |

La alternativa —browser llamando directo a Railway con CORS habilitado—
pierde en tres puntos a la vez: obliga a cambiar `ai-service/app/main.py` (una
capability existente que se modifica sin necesidad funcional propia), publica
la forma exacta de la API al cliente, y deja la URL de Railway como única
barrera de un servicio que **hoy no tiene autenticación** (`app/config.py` no
define ningún token — ver `.env.example`). Cuando haga falta autenticar, el
proxy es el único archivo que hay que tocar para agregar el header.

## Vercel AI SDK: la condición de entrada

El curso es explícito en que **el cliente nunca habla con OpenAI o Anthropic
directamente**: solo hace POST al servicio FastAPI, que es quien maneja
guardrails, llamadas al modelo y cachés. Ese límite es el que hace que toda la
lógica de IA viva en un solo proyecto.

El SDK de Vercel se usa habitualmente para lo contrario —una route handler que
llama al proveedor y streamea al browser—, y en esa forma rompería el límite.
Así que la condición es doble:

1. **Cuándo entra:** cuando el servicio IA exponga un endpoint de generación
   que streamee. Hoy no existe; `openspec/project.md` lo lista como no
   construido, y es la pieza que falta para que esto sea un RAG y no un
   buscador.
2. **Cómo entra:** solo las primitivas de UI (`useChat` / `useCompletion`)
   apuntadas al Route Handler propio, que reenvía el stream del servicio IA.
   Ninguna clave de proveedor en `business-backend/`, ni siquiera del lado del
   servidor.

Instalarlo antes de eso sería una dependencia sin uso, y elegir hoy la forma en
que se va a consumir un endpoint que todavía no se diseñó es diseñarlo mal.

## shadcn/ui: por qué el código de los componentes entra al repo

shadcn/ui no se instala como librería: su CLI **copia el código fuente de cada
componente** dentro del proyecto. Suena a desventaja y es lo que se quiere acá,
por dos razones concretas de estas pantallas:

- Los resultados de búsqueda tienen que mostrar procedencia densa —documento,
  sección, score, ramas que lo encontraron— y eso termina siendo un `Card`
  bastante intervenido. Con los componentes en el repo, la intervención es una
  edición; con una librería, es un `styled(...)` peleando contra el default.
- Los componentes copiados no se actualizan solos, y para un proyecto que se
  entrega y se evalúa eso es estabilidad, no deuda.

Se copian **solo los componentes que cada pantalla usa**. Un `components/ui/`
con cuarenta archivos de los que se usan seis es la versión shadcn de
pre-construir capas vacías.

## Las tres pantallas, y por qué esas

| pantalla | endpoint(s) | qué demuestra |
|---|---|---|
| Búsqueda | `GET /search` | recuperación híbrida y procedencia, sin generación |
| Vista previa de ingesta | `POST /documents/ingest[-file]` | el chunking de un documento, sin persistir |
| Reconstrucción de corpus | `POST /corpus/rebuild`, `GET /corpus/jobs[/{id}]` | el pipeline batch, con el guard de `reset` intacto |

La pantalla de búsqueda es la única que muestra el sistema entero funcionando,
así que es la que más presupuesto de diseño se lleva: filtros
(`module_code`, `window_type_name`, `limit`) y los tres toggles que el endpoint
expone (`lexical`, `split`, `rerank`), cada uno con el número medido al lado —
el propio `search.py` documenta que `lexical` baja el acierto@1 de 77% a 48%, y
que `rerank` sube p@10 de 0,140 a 0,171 a costa de 3× la latencia. Un toggle
sin ese contexto invita a apagar lo que conviene dejar prendido.

## Los errores del servicio son de primera clase

El curso trata `GuardrailViolation` como un error propio del cliente, no como
una falla genérica: el servicio devuelve 400 con su razón y la UI la muestra.
Acá los dos errores documentados son otros, y merecen el mismo trato:

- **409 en `POST /corpus/rebuild`** — ya hay un job corriendo. Dos rebuilds
  escribirían el mismo directorio y la misma tabla. La UI lo muestra como
  estado ("hay una reconstrucción en curso", con link al job), no como error.
- **400 en `POST /corpus/rebuild`** — `confirm_tenant_id` / `confirm_doc_version`
  no coinciden. No debería llegar a pasar, porque la pantalla exige la
  confirmación antes de habilitar el envío; si igual ocurre, se muestra el
  mensaje del servicio tal cual.

Y el guard se repite en la UI a propósito: `app/api/corpus.py` exige esos dos
campos exactos para que un `reset=true` suelto no vacíe una base. Una pantalla
que mande ese `reset=true` con un checkbox reintroduce, un nivel más arriba, el
riesgo que el endpoint fue diseñado para evitar. Los valores de confirmación
salen de una llamada de solo lectura, no de una constante en el código de la
UI: una constante desactualizada convertiría el guard en un trámite.

## CI: un job por proyecto, ningún job que despliegue

El `ci.yml` del curso termina en un job que hace SSH a un EC2 y levanta
`docker compose`. Acá no hay EC2: Railway y Vercel despliegan desde GitHub por
su propia integración, con rollback incluido. Reproducir ese job sería
reimplementar en YAML lo que las dos plataformas ya hacen.

Lo que sí se reutiliza es su Etapa 0: `dorny/paths-filter` calcula una vez qué
cambió y cada job de test corre solo si su carpeta se tocó. Después de
`move-service-to-ai-service` los filtros son dos rutas limpias —`ai-service/**`
y `business-backend/**`—, que es un beneficio concreto de haber movido el
servicio: sin la mudanza, el filtro del servicio IA sería una lista de seis
rutas sueltas de la raíz que hay que mantener a mano.

El filtro equivalente del lado de cada plataforma (Railway "Watch Paths",
Vercel "Ignored Build Step") vive en la configuración de cada una, no en el
repo, y queda documentado en `tasks.md`.
