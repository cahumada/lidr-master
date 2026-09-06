import assert from "node:assert/strict"
import { test } from "node:test"

import {
  refuseDelete,
  refuseDisable,
  refuseRoleChange,
  type TargetAccount,
} from "./guards"

const ADMIN: TargetAccount = {
  id: "otro",
  role: "administrador",
  disabledAt: null,
}
const USUARIO: TargetAccount = { id: "otro", role: "usuario", disabledAt: null }

test("un administrador promueve a un usuario", () => {
  assert.equal(refuseRoleChange("yo", USUARIO, "administrador", 1), null)
})

test("nadie cambia su propio rol", () => {
  const self: TargetAccount = { ...ADMIN, id: "yo" }
  assert.ok(refuseRoleChange("yo", self, "usuario", 5))
  // Ni siquiera para promoverse, y ni siquiera sobrando administradores.
  // || Not even to promote themselves, and not even with admins to spare.
  const selfUser: TargetAccount = { ...USUARIO, id: "yo" }
  assert.ok(refuseRoleChange("yo", selfUser, "administrador", 5))
})

test("el último administrador habilitado no se puede degradar", () => {
  assert.ok(refuseRoleChange("yo", ADMIN, "usuario", 0))
  assert.equal(refuseRoleChange("yo", ADMIN, "usuario", 1), null)
})

test("el último administrador habilitado no se puede deshabilitar ni borrar", () => {
  assert.ok(refuseDisable(ADMIN, 0))
  assert.ok(refuseDelete("yo", ADMIN, 0))
  assert.equal(refuseDisable(ADMIN, 1), null)
  assert.equal(refuseDelete("yo", ADMIN, 1), null)
})

test("un administrador ya deshabilitado no cuenta como el último", () => {
  // No sostiene la consola, así que degradarlo o borrarlo no la deja sin
  // administración.
  // || A disabled admin is not holding the console up.
  const disabled: TargetAccount = { ...ADMIN, disabledAt: new Date() }
  assert.equal(refuseRoleChange("yo", disabled, "usuario", 0), null)
  assert.equal(refuseDelete("yo", disabled, 0), null)
})

test("deshabilitar a alguien ya deshabilitado no se rechaza", () => {
  // La operación es idempotente; rechazarla sería un error inventado.
  // || The operation is idempotent.
  const disabled: TargetAccount = { ...ADMIN, disabledAt: new Date() }
  assert.equal(refuseDisable(disabled, 0), null)
})

test("un usuario sin rol de administrador nunca dispara la baranda", () => {
  assert.equal(refuseDisable(USUARIO, 0), null)
  assert.equal(refuseDelete("yo", USUARIO, 0), null)
})

test("cambiar el rol al que ya tiene no dispara la baranda", () => {
  // Guardar «administrador» sobre un administrador no degrada a nadie.
  // || Saving "administrador" over an administrator demotes nobody.
  assert.equal(refuseRoleChange("yo", ADMIN, "administrador", 0), null)
})

test("nadie borra su propia cuenta", () => {
  const self: TargetAccount = { ...USUARIO, id: "yo" }
  assert.ok(refuseDelete("yo", self, 5))
})
