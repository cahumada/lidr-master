# Diseño — ledger en Configuración, último tiro en el chat

El contrato ya está en `add-llm-usage-accounting`. Acá se decide
dónde se ve y qué no se inventa.

---

## 1. Una pantalla nueva, no un panel adentro del chat

El agregado del tenant (totales, por modelo, rango de fechas) no
es un dato del hilo. Meterlo en `/answer` mezclaría dos escalas,
el mismo error que `add-answer-history-console` evitó al dejar
la lista de hilos *adentro* del chat y no en el sidebar.

| Alternativa | Por qué pierde |
|---|---|
| Card en `/answer` | El chat ya tiene historial, anchors y progreso. Un ledger de tenant no cabe sin esconderse. |
| Ficha extra en `/models` | Modelos configura claves y catálogo. Mezclar «qué modelos hay» con «cuánto se cobró» es el mismo ruido que un dashboard en la portada. |
| `/usage` en Configuración, admin | Gana. Misma audiencia que Modelos. `PageFrame` + tabla, el patrón de Corpus. |

El ítem es `administrador`. El gasto es del tenant, no de un
turno. Un consultor que solo chatea no administra proveedores.

## 2. El chat pinta la última completion, no la suma

El body agentico trae el `usage` de **esa** corrida. Un `adjust`
deja dos filas en el ledger y un solo número en el 200 — el de
la respuesta que se está viendo. Eso ya lo fijó el servicio.

`ChatTurn` gana `usage` opcional. Se llena al cerrar un turno
en vivo. `historyToTurns` **no** lo rellena: `HistoryTurn` no
tiene el campo, y poner ceros se leería como «esta reapertura
no costó nada». Ausente ≠ no reportado.

Quien quiera el total de un hilo va a `/usage` y filtra por
`session_id`, o lo deja para un change que pida ese recorte
en el chat. No se hace un `GET` extra por cada reapertura.

## 3. El BFF no recorta por usuario

Igual que `GET /answer/sessions`: el servicio no autentica.
Filtrar el summary en el Route Handler con el `user.id` de
Auth.js mentiría — cualquiera que alcance Railway ve el
tenant entero. La pantalla admin es presentación, no un
segundo techo. El layout `(admin)` ya cierra la ruta.

## 4. Degradar, no fingir

Si `GET /usage/summary` no existe (404) o el servicio no
responde, `/usage` llega con ceros + el `error` del BFF. El
chat no depende de ese GET. Inventar un summary local
sumando lo que el browser vio en la sesión sería otro ledger,
desfasado del Postgres.

## 5. Sin precio

Modelos ya enlaza a la página oficial de tarifas. Multiplicar
tokens × una tablita hardcodeada miente la semana que cambia
la tarifa. Este change muestra lo que el proveedor reportó.
