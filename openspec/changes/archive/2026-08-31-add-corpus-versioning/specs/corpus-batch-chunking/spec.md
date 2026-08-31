# corpus-batch-chunking Delta Specification

## ADDED Requirements

### Requirement: La corrida DEBE emitir un manifiesto del corpus
Sin manifiesto, los JSON por módulo son una pila de chunks sin procedencia: no
dicen de qué cliente son, de qué versión de la documentación, ni cuándo se
generaron. El manifiesto (`<out>/manifest.json`) es la declaración autoritativa
de esa corrida, replicando el `manifest` de `corpus_schema.json`.

#### Scenario: Contenido del manifiesto
- **WHEN** la corrida termina
- **THEN** `<out>/manifest.json` lleva `corpus_id`, `tenant_id`, `doc_version`,
  `generated_at`, `source_root`, los módulos procesados y los totales de
  documentos, chunks y tokens

#### Scenario: Identidad sobreescribible por corrida
- **WHEN** la corrida recibe `--tenant` o `--doc-version`
- **THEN** esos valores se usan en el estampado y en el manifiesto, en vez de
  los de la configuración
