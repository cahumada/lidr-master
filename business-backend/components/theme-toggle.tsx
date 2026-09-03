"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useLayoutEffect } from "react";

import { Button } from "@/components/ui/button";
import {
  applyTheme,
  readStoredTheme,
  resolveTheme,
  storeTheme,
  watchSystemTheme,
} from "@/lib/theme";

/**
 * Light/dark switch. Holds no React state on purpose: the current theme lives
 * in one place — the `dark` class on `<html>` — and the two icons swap with the
 * `dark:` variant, in CSS. State here would be a second copy of that truth,
 * rendered on the server where the theme is unknowable, which is a hydration
 * mismatch waiting to happen.
 *
 * || Interruptor claro/oscuro. No guarda estado de React a propósito: el tema
 * vigente vive en un solo lugar —la clase `dark` en `<html>`— y los dos íconos
 * se alternan con la variante `dark:`, en CSS. Un estado acá sería una segunda
 * copia de esa verdad, renderizada en el servidor donde el tema es
 * desconocible: un desajuste de hidratación esperando pasar.
 */
export function ThemeToggle() {
  // Re-applies the theme after React's dev-only Strict Mode remount, which
  // resets `<html>` to the attributes it manages from JSX and drops the class
  // the inline script set. A no-op in production.
  // || Reaplica el tema después del remount de Strict Mode (solo en dev), que
  // deja `<html>` con los atributos que React maneja desde el JSX y descarta la
  // clase que puso el script inline. En producción no hace nada.
  useLayoutEffect(() => {
    applyTheme(resolveTheme());
  }, []);

  // While the user has not chosen explicitly, follow the OS as it changes.
  // || Mientras el usuario no eligió explícitamente, seguir al sistema operativo.
  useEffect(
    () =>
      watchSystemTheme((theme) => {
        if (readStoredTheme() === null) applyTheme(theme);
      }),
    [],
  );

  function toggle() {
    const next = resolveTheme() === "dark" ? "light" : "dark";
    storeTheme(next);
    applyTheme(next);
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label="Alternar entre tema claro y oscuro"
      title="Alternar entre tema claro y oscuro"
    >
      <Sun className="hidden dark:block" />
      <Moon className="block dark:hidden" />
    </Button>
  );
}
