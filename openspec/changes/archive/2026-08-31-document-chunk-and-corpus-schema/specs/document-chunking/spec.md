# document-chunking Delta Specification

## ADDED Requirements

### Requirement: El título de un bloque NUNCA DEBE ser su propia línea de id
El título propio de un bloque es su heading H1 y nada más. Un bloque que
arranca en su propia línea de id no tiene título propio y DEBE caer al título
del documento, porque las dos alternativas producen un header que no dice nada
de la transacción: tomar la línea de id daba
`[Documento: OP010 - `**(OP010)**`]` (133 documentos, 2968 chunks), y tomar la
primera línea de prosa del cuerpo daba
`[Documento: CA014 - Permite consultar y modificar.]`.

El título llega al header contextual de cada chunk, así que es lo que un chunk
recuperado usa para decir a qué transacción pertenece.

#### Scenario: Bloque que arranca en su línea de id
- **WHEN** un bloque no tiene H1 propio, como en un documento cuya línea de id
  es su primer contenido
- **THEN** su título es el del documento, p. ej. "Coberturas de la póliza
  individual o certificado" para CA014
- **AND** nunca es el bloque de id ni una línea de prosa del cuerpo

#### Scenario: Bloque con su propio H1
- **WHEN** un bloque abre con `# Solicitud de código a actualizar`
- **THEN** ese heading es su título
