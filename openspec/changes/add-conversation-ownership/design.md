# Diseño

## 1. Por qué un header alcanza, si antes no alcanzaba

`add-console-authentication` cerró la puerta a mandarle identidad al servicio con
una razón concreta: *"mandárselo a un servicio que no autentica a nadie deja que
cualquiera que alcance la URL pública lea el corpus de otro cliente"*. Esa frase
es sobre **tenant**, y era correcta.

Dos cosas cambiaron. `add-service-authentication` dejó al servicio cerrado detrás
de un `SERVICE_TOKEN`, y ese token vive en un solo lugar
(`lib/ai-service/base-client.ts`, `server-only`). Así que hoy **quien puede
mandar el header es exactamente quien ya puede mandar el token**: un header
emitido ahí no agrega superficie, viaja adentro de la que ya existe.

Y la apuesta es distinta. Un tenant equivocado deja leer el corpus de otro
cliente. Un `owner_id` equivocado deja leer la conversación de otro usuario del
mismo despliegue: peor que nada, mucho menos que eso. No hay razón para que el
problema chico espere al grande.

## 2. Sin identidad no es "ver todo"

La decisión que más fácil se equivoca: qué hace el servicio con un request que no
trae `X-Console-User`.

Si la ausencia significara *"sin filtro"*, el arreglo se esquivaría **quitando un
header**. Sería una autorización que se apaga sola, que es la misma clase de
defecto que `requireAdmin` evita al no confiar en que el link esté oculto.

Así que la ausencia es su propio valor: `owner_id IS NULL`. Un request sin
identidad ve las conversaciones sin dueño y ninguna otra. Cae bien en los tres
casos que existen:

- La consola siempre manda identidad → ve las propias.
- Los evals y los scripts no mandan → crean y leen las suyas, sin dueño, y no
  ven ni ensucian las de las personas.
- Un curioso con el token y sin header no ve nada de nadie.

## 3. 404 y no 403

Pedir la conversación de otro responde **404**, el mismo que "desconocido o
vencido". Un 403 diría *"existe, pero no es tuya"*, que es información sobre la
actividad de otra persona.

El router ya tomó esta decisión dos veces: `_UNKNOWN` cubre el id que no existe y
el que venció, *"expiry is indistinguishable from absence"*. Ajena es la tercera
cara de lo mismo, y merece la misma respuesta.

## 4. El dueño es opaco

`owner_id` guarda el `User.id` de la consola —un cuid—, no el email. El servicio
compara cadenas y nunca aprende quién es nadie: no necesita PII para resolver esta
autorización, y no tenerla es una fuga menos el día que alguien lea la tabla.

Efecto de borde deliberado: el servicio **no puede** poner el nombre del dueño en
un listado. Si algún día hace falta mostrarlo, lo resuelve el BFF, que sí tiene la
tabla de usuarios. Es el lado correcto para que viva esa traducción.

## 5. Filtrar en la query, no después de leer

El filtro va en el `WHERE`, no en un `if` sobre lo que volvió. Filtrar después
funciona igual hasta el día que alguien agrega un `limit`: con paginación, leer 50
y descartar las ajenas devuelve páginas cortas y una última página que miente.
Además una fila ajena que se lee y se tira ya pasó por la red y por el log.

## 6. Las filas viejas se adjudican

`owner_id` entra `NULL`able. Sin eso la migración tendría que inventar un dueño
para lo que ya existe, y un dueño inventado es peor que ninguno.

Con la regla de §2, las conversaciones actuales quedan **invisibles en la consola
y enteras en la base**. Un script de una sola vez les pone el `owner_id` que se le
pase. Adjudicar es reversible y explícito; borrar no es ninguna de las dos.
