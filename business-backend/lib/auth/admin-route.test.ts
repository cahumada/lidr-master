import assert from "node:assert/strict"
import { test } from "node:test"

import { mayCallAdminRoute } from "./roles"

test("un administrador puede llamar una ruta de administración", () => {
  assert.equal(mayCallAdminRoute("administrador"), true)
})

test("un usuario no puede", () => {
  assert.equal(mayCallAdminRoute("usuario"), false)
})

test("un rol desconocido cae al menos privilegiado, no al más", () => {
  // Un token con un rol que este build no conoce no puede ser administrador.
  assert.equal(mayCallAdminRoute("superadmin"), false)
  assert.equal(mayCallAdminRoute("ADMINISTRADOR"), false)
})

test("sin rol tampoco", () => {
  assert.equal(mayCallAdminRoute(undefined), false)
  assert.equal(mayCallAdminRoute(null), false)
  assert.equal(mayCallAdminRoute(""), false)
})
