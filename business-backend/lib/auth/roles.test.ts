import assert from "node:assert/strict"
import { test } from "node:test"

import { asRole, canAccess, isAdminOnly, DEFAULT_ROLE } from "./roles"

test("las pantallas abiertas lo son para cualquier rol", () => {
  for (const path of ["/", "/answer", "/search", "/documents"]) {
    assert.equal(canAccess("usuario", path), true, path)
    assert.equal(canAccess("administrador", path), true, path)
  }
})

test("las pantallas de administración exigen el rol", () => {
  for (const path of ["/agents", "/models", "/corpus", "/users"]) {
    assert.equal(canAccess("usuario", path), false, path)
    assert.equal(canAccess("administrador", path), true, path)
  }
})

test("una subpantalla hereda de su sección", () => {
  // `/agents/flow` no está listada; hereda de `/agents` por prefijo. Sin esto,
  // una subpantalla nueva nacería más floja que su padre.
  // || `/agents/flow` is not listed; it inherits from `/agents` by prefix.
  assert.equal(isAdminOnly("/agents/flow"), true)
  assert.equal(canAccess("usuario", "/agents/flow"), false)
})

test("el prefijo no matchea una ruta que solo empieza igual", () => {
  assert.equal(isAdminOnly("/agents-publicos"), false)
  assert.equal(isAdminOnly("/usersomething"), false)
})

test("sin rol no se alcanza una pantalla de administración", () => {
  assert.equal(canAccess(undefined, "/models"), false)
})

test("asRole aterriza cualquier valor desconocido en el menos privilegiado", () => {
  // Lo que sale de un JWT es `unknown`. Un claim ausente, viejo o inventado
  // NUNCA puede leerse como administrador.
  // || What comes out of a JWT is `unknown`. A missing, stale or invented
  // claim must NEVER read as administrator.
  for (const value of [undefined, null, "", "admin", "ADMINISTRADOR", 1, {}]) {
    assert.equal(asRole(value), DEFAULT_ROLE, String(value))
  }
  assert.equal(asRole("administrador"), "administrador")
  assert.equal(asRole("usuario"), "usuario")
})
