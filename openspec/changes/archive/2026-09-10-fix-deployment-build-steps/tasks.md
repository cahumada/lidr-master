# Tareas

## 1. Consola (Vercel)

- [x] `business-backend/package.json`: `build` corre `prisma generate` antes de
      `next build`.
- [x] `business-backend/package.json`: script `db:deploy` para
      `prisma migrate deploy`, explícito y fuera del build.
- [x] Verificar que el build compila con el cliente Prisma borrado — la
      condición del clone limpio, no la del working copy de siempre.

## 2. Servicio (Railway)

- [x] `ai-service/Dockerfile`: el `CMD` corre `alembic upgrade head` y recién
      después `uvicorn`, con el porqué escrito (una sola instancia).
- [x] Verificar que la imagen construye.

## 3. Documentación

- [x] `README.md`: la tabla de despliegue lista TODAS las variables de Vercel,
      no solo `AI_SERVICE_URL`.
- [x] `README.md`: los pasos que no viven en el repo — redirect URI de Google y
      alta del primer usuario— quedan escritos donde se los busca.
- [x] `README.md`: "próximos pasos" refleja qué queda realmente pendiente
      (verificar la URL viva), no lo que este change cierra.

## 4. Cierre

- [x] `python scripts/validate_specs.py` sin errores.
