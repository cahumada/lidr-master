import assert from "node:assert/strict"
import test from "node:test"

import { CONSOLE_USER_HEADER, consoleUserHeaderFor } from "./console-user"

test("un usuario logueado viaja en el header", () => {
  assert.deepEqual(consoleUserHeaderFor("cm4xk2p0000abc"), {
    [CONSOLE_USER_HEADER]: "cm4xk2p0000abc",
  })
})

test("sin sesión no va header, y nunca un valor inventado", () => {
  // El servicio lee la ausencia como «las que tampoco tienen dueño»: la falla
  // es no ver nada, no ver las de todos.
  // || The service reads absence as the ownerless bucket: the failure mode is
  // seeing nothing, not seeing everybody's.
  assert.deepEqual(consoleUserHeaderFor(undefined), {})
  assert.deepEqual(consoleUserHeaderFor(null), {})
  assert.deepEqual(consoleUserHeaderFor("   "), {})
})

test("un id demasiado largo se descarta y no se corta", () => {
  // Cortarlo haría colisionar dos usuarios distintos en un mismo dueño, que es
  // justo la falla que esto viene a evitar.
  // || Cutting it would collide two different users into one owner.
  assert.deepEqual(consoleUserHeaderFor("x".repeat(65)), {})
})
