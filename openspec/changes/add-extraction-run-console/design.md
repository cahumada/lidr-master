## Qué significa «completa»

El enunciado pide ver todas las corridas y seleccionar solo las
completadas. En `visualtime.extraction_runs` hay dos cosas que se
parecen y no lo son:

| Campo | Qué es | ¿Gate? |
|---|---|---|
| `status` | Estado que le pone el extractor. Arranca en `partial`. | No. El dominio §2 pide **no** exigirlo. |
| `loaded_data` | Si `business_data` de esa corrida está cargado. | Sí. El árbol de `WINDOWS` vive ahí. |
| `loaded_metadata` / `loaded_dependencies` | Diccionario y grafo. Independientes. | Informan; no activan. |

El contrato ya lo resolvió: `can_activate = loaded_data`, y
activar sin datos es **409**. La consola no inventa un segundo
filtro. Muestra `status` y las tres banderas para que se entienda
*por qué* una fila no se puede elegir.

Si más adelante el extractor publica un `status` estable
(`completed` / `failed`) y se quiere **además** de `loaded_data`,
eso es un change de `ai-service` con medición. Fingirlo en el BFF
haría que el operador crea que el servicio rechaza lo que el
servicio aceptaría.

## Dónde vive la pantalla

`(console)/(admin)/business-db` → `/business-db`. Escribe
configuración, así que el grupo **es** el gate. Módulo
Configuración, junto a Modelos y Uso: elegir la corrida es «con
qué trabaja el servicio», no «reconstruir el corpus markdown»
(`/corpus` es RAG).

Alternativa descartada: meterla adentro de Corpus. Mezclaría el
rebuild del markdown con la selección del mirror, que son dos
autoridades y dos ciclos de vida.

## Quién aparece en `activated_by`

El servicio no tiene identidad de usuario: autentica al llamador
con un token compartido y guarda lo que quien llama **declara**.
La consola sí tiene sesión. El Server Component pasa
`session.user.email` (o `name`) al cliente; el POST lo manda; el
handler lo reenvía. El cliente de `lib/ai-service/` no llama a
`auth()` — `lib/auth/` y `lib/ai-service/` no se importan entre
sí.

No inventar `"unknown"`: sería indistinguible de alguien que se
llame así y se leería como registro.

## Confirmación

Activar cambia el árbol de navegación, el estado de ventana y —si
está el bloque de base— qué filas viajan al prompt. Un click
suelto es barato de más. Confirmación en la propia pantalla
(texto + segundo click o `window.confirm`), sin toast ni
dependencia nueva. El 409/404 posteriores se muestran con el
`error` del BFF; no se tragan.
