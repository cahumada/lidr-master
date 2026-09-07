import assert from "node:assert/strict"
import { test } from "node:test"

import { hashPassword, verifyPassword } from "./password"

/**
 * Hashing and verification. Slow on purpose — bcrypt with cost 12 is about a
 * quarter second per call, and that is the point of it, so this file stays
 * short rather than exhaustive.
 * || Hasheo y verificación. Lentos a propósito: bcrypt con costo 12 tarda un
 * cuarto de segundo por llamada, y esa es justamente su razón de ser.
 */

test("una contraseña correcta verifica", async () => {
  const hash = await hashPassword("una-contraseña-larga")
  assert.equal(await verifyPassword("una-contraseña-larga", hash), true)
})

test("una contraseña incorrecta no verifica", async () => {
  const hash = await hashPassword("una-contraseña-larga")
  assert.equal(await verifyPassword("otra-contraseña-larga", hash), false)
})

test("el hash no contiene la contraseña", async () => {
  const hash = await hashPassword("una-contraseña-larga")
  assert.ok(!hash.includes("una-contraseña-larga"))
})

test("dos hashes de la misma contraseña difieren", async () => {
  // El salt va adentro del hash. Sin esto, dos cuentas con la misma
  // contraseña se reconocerían mirando la tabla.
  // || The salt lives inside the hash. Without it, two accounts sharing a
  // password would be recognisable from the table alone.
  const a = await hashPassword("una-contraseña-larga")
  const b = await hashPassword("una-contraseña-larga")
  assert.notEqual(a, b)
})

test("una cuenta sin contraseña no verifica, y no lanza", async () => {
  // Un usuario que solo entra por Google tiene `passwordHash = null`.
  // || A Google-only user has `passwordHash = null`.
  assert.equal(await verifyPassword("lo-que-sea", null), false)
  assert.equal(await verifyPassword("lo-que-sea", undefined), false)
})

test("una contraseña vacía no verifica contra un hash válido", async () => {
  const hash = await hashPassword("una-contraseña-larga")
  assert.equal(await verifyPassword("", hash), false)
})

test("hashear una contraseña vacía lanza", async () => {
  await assert.rejects(() => hashPassword(""))
})
