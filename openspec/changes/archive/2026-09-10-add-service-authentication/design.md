# Diseño

## 1. Un token compartido, no un modelo de usuarios

El servicio tiene **un** cliente legítimo: el BFF de la consola, que corre en el
servidor. Las personas ya están autenticadas del otro lado —
`add-console-authentication` pone dos roles en el token de sesión y gatea las
rutas— y ese trabajo no se puede reusar acá: la sesión de Auth.js vive en la
consola, no viaja al servicio, y hacerla viajar convertiría al servicio en un
segundo verificador del mismo modelo.

Lo que el servicio necesita saber no es *quién* pregunta, es *si el que llama es
mi consola*. Eso es un secreto compartido.

**Alternativa descartada — llevar la identidad del usuario al servicio.** Es
tentador porque arreglaría de paso la atribución del gasto en el ledger. Pero
significa que el servicio confíe en un claim que el BFF le pasa: sin verificar
la firma de la sesión, ese claim es tan bueno como el token igual; y
verificándola, el servicio necesita el secreto de Auth.js y pasa a conocer el
modelo de usuarios. Dos sistemas de identidad para una consola de un tenant.

**Alternativa descartada — red privada.** Railway sí ofrece red interna, pero el
BFF corre en Vercel: es otro proveedor y el tráfico sale a internet. No hay
private networking que cubra ese salto sin un túnel pago.

## 2. Todos los endpoints menos `/health`

La tentación es cerrar solo los 23 que mutan y dejar las lecturas abiertas
—«total, solo leen»—. No:

- `GET /search` **llama al embedder en cada consulta**. Es una lectura que cuesta
  dinero por llamada.
- `GET /config` revela el catálogo de modelos, los proveedores configurados y si
  el almacenamiento de credenciales está habilitado. No es un secreto, pero es
  reconocimiento gratis.
- `GET /usage/summary` expone el consumo del tenant.

`/health` queda abierto porque es el healthcheck del despliegue
(`README.md`: healthcheck → `/health`). Cerrarlo haría que Railway marque el
servicio como caído y lo reinicie en loop: la peor manera posible de romper esto.

## 3. Falla cerrado en producción, abierto en desarrollo — y lo dice

Esta es la decisión que más importa y la más fácil de hacer mal.

Si el token es obligatorio siempre, `uv run pytest`, `scripts/eval_generation.py`
y cualquier `curl` local necesitan configurarlo, y alguien va a terminar
hardcodeándolo en un conftest. Si es opcional siempre, un despliegue que se
olvidó de la variable queda **abierto y con aspecto de cerrado**, que es peor que
el estado de hoy: hoy al menos está declarado que no hay auth.

La salida usa un setting que ya existe:

| `APP_ENV` | sin `SERVICE_TOKEN` |
|---|---|
| `development` / `staging` | arranca **abierto**, con un warning en el log de arranque |
| `production` | **se niega a arrancar**, con el nombre de la variable que falta |

El warning no es decorativo: es la única señal de que un entorno está abierto, y
va con las palabras que hacen falta para buscarlo después.

**Alternativa descartada — un default generado al arrancar.** Un token que el
servicio se inventa no lo puede conocer el BFF, así que la consola se rompería;
y si se persiste, aparece un secreto en la base que nadie rotó.

## 4. El token no puede llegar al browser, y eso ya está garantizado

`base-client.ts` es `server-only` —importarlo desde un Client Component es un
error de build— y `call()` es el único lugar donde se hace `fetch` contra el
servicio. El header se agrega ahí y en ningún otro lado, por la misma razón por
la que `AI_SERVICE_URL` vive ahí: la garantía es estructural, no una convención.

La variable **no** lleva prefijo `NEXT_PUBLIC_`. Ese prefijo es exactamente el
mecanismo que la expondría.

## 5. 401 y sin detalle

401 y no 403: 403 dice «te conozco y no podés», y el servicio no conoce a nadie.
Va con `WWW-Authenticate`, que es lo que un cliente HTTP espera para saber cómo
autenticarse.

El cuerpo **no** distingue «faltaba el token» de «el token no coincide». La
diferencia solo le sirve a quien está probando tokens.

## 6. Lo que este change NO arregla, y conviene no confundirlo

El token corta el acceso **anónimo**. No corta:

- **El gasto.** Quien tenga el token puede seguir llamando `/answer` sin tope.
  El ledger lo registra, pero registrar no es limitar.
- **La atribución.** El gasto sigue quedando a nombre del portador del token
  —el BFF— y no de la persona que preguntó. El servicio no tiene identidad de
  usuario y este change no se la agrega.

Las dos son changes propios. Escribirlas acá es para que nadie lea «el servicio
ya está autenticado» y deduzca que también está acotado.
