# corpus-rebuild Delta Specification

## ADDED Requirements

### Requirement: Los artefactos generados DEBEN vivir bajo su versión
El corpus troceado y el sidecar de vectores son de una versión concreta de la
documentación. Con rutas fijas, re-trocear una versión nueva **destruye los
artefactos de la anterior** en el lugar, y con ellos la posibilidad de recargarla
sin volver a pagar por embeberla.

Demostrado: de 384 chunks de un primer corpus, sobrevivieron **0** al trocear un
segundo encima.

El tenant NO va en la ruta: un proceso sirve exactamente un tenant
—`Settings.TENANT_ID` es un valor único leído en todos lados— así que un segmento
por tenant sería un nivel de directorio que nunca tiene hermanos.

#### Scenario: Dos versiones conviven
- **WHEN** se trocean dos versiones de la documentación
- **THEN** cada una queda en su propio directorio y ninguna pisa a la otra

#### Scenario: El nombre del directorio es usable
- **WHEN** un `doc_version` tiene espacios o puntos
- **THEN** el directorio lleva un nombre seguro para el filesystem

#### Scenario: Dos versiones parecidas no comparten directorio
- **WHEN** dos `doc_version` distintos producen el mismo slug
- **THEN** sus directorios siguen siendo distintos, porque el nombre lleva una
  huella del valor original

#### Scenario: El manifiesto tiene que coincidir con su directorio
- **WHEN** el manifiesto de un directorio declara otra versión que la que nombra
  al directorio
- **THEN** se levanta un error, porque cargar un corpus atribuyéndolo a otra
  versión no se ve después: las filas quedan con la versión equivocada y el
  prune de la versión real las borra

#### Scenario: El reporte queda con los artefactos
- **WHEN** un paso escribe su reporte legible
- **THEN** queda en el mismo directorio que los artefactos de esa versión, y no
  en la base
