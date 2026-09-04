# Implementation Tasks

## 1. Specs
- [x] 1.1 Change OpenSpec con proposal, design, tasks y delta de `web-console`.
- [x] 1.2 `python scripts/validate_specs.py` pasa.

## 2. Shell y navegación
- [x] 2.1 Copiar sidebar, separator, tooltip, sheet y scroll-area de shadcn.
- [x] 2.2 Shell con sidebar por módulos (Respuesta, RAG, Configuración) y
      conmutador de tema; tokens de `--sidebar-*` y de tema, sin colores
      literales nuevos.
- [x] 2.3 Portada agrupada por los tres módulos.

## 3. Configuración
- [x] 3.1 Pantalla `/agents` solo tipos de agentes (configurables y
      deterministas).
- [x] 3.2 Pantalla `/models` con proveedores y catálogo de modelos.

## 4. Respuesta como chat
- [x] 4.1 Hilo de sesión: burbujas usuario/asistente, compositor abajo,
      cada pregunta appendea un turno.
- [x] 4.2 Progreso en vivo, gate de revisión, citas y traza de enrutado
      siguen visibles dentro del turno.
- [x] 4.3 Knobs de retrieval (filtros y toggles medidos) en un panel
      aparte del compositor.

## 5. Verificar
- [x] 5.1 `pnpm lint` y `pnpm build` desde `business-backend/`.
- [ ] 5.2 Recorrer los tres módulos en claro y oscuro.
