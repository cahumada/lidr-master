# web-console Delta Specification

## ADDED Requirements

### Requirement: La respuesta del asistente se muestra como markdown

La pantalla de respuesta SHALL renderizar el texto del asistente como
markdown —negritas, listas, encabezados, código y tablas— en vez de mostrarlo
como texto plano. El prompt de síntesis le pide explícitamente al modelo que
estructure la respuesta y que cierre con un bloque de fuentes; mostrarla sin
formato tira esa estructura y deja los asteriscos a la vista.

El renderizado SHALL ser sin HTML crudo. El texto viene de un modelo sobre
contenido de corpus, y habilitar markup arbitrario desde una fuente que nadie
revisa es una decisión de seguridad, no de estilo.

La pregunta del usuario NO se renderiza como markdown: la escribió una
persona y sus asteriscos son literales. Los avisos del sistema —contexto
recortado, pregunta resuelta, respuesta incompleta— tampoco: no son contenido
del modelo.

#### Scenario: negritas y listas

- **WHEN** la respuesta trae `**texto**` y una lista con guiones
- **THEN** se ven en negrita y como lista
- **AND** los asteriscos y los guiones no se muestran literales

#### Scenario: el cierre de fuentes se distingue del cuerpo

- **WHEN** la respuesta termina con el bloque `Fuentes citadas:` y su lista
- **THEN** esa lista se ve como lista y no como prosa corrida

#### Scenario: HTML embebido no se ejecuta

- **WHEN** el texto de la respuesta contiene una etiqueta HTML
- **THEN** se muestra como texto
- **AND** no se inserta en el DOM como markup

#### Scenario: una tabla ancha no rompe el layout

- **WHEN** la respuesta trae una tabla más ancha que la burbuja del turno
- **THEN** la tabla scrollea horizontalmente en su propio contenedor
- **AND** la página no scrollea horizontalmente

#### Scenario: la pregunta del usuario queda literal

- **WHEN** el usuario escribe una pregunta que contiene `**`
- **THEN** el hilo muestra esos caracteres tal como los escribió
