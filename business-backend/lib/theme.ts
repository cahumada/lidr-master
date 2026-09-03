/**
 * Light/dark theme: the one place that knows how the choice is stored and how
 * it reaches the DOM. Both the inline script in the root layout and the toggle
 * component read from here, so they can never disagree about the storage key
 * or the class name.
 *
 * || Tema claro/oscuro: el único lugar que sabe cómo se guarda la elección y
 * cómo llega al DOM. Tanto el script inline del layout raíz como el conmutador
 * leen de acá, así no pueden discrepar sobre la clave de storage ni el nombre
 * de la clase.
 */

export type Theme = "light" | "dark";

/** `localStorage` key holding the explicit choice, if the user made one.
 *  || Clave de `localStorage` con la elección explícita, si el usuario hizo una. */
export const THEME_STORAGE_KEY = "theme";

/** The class Tailwind's `dark:` variant keys off (`app/globals.css`).
 *  || La clase de la que depende la variante `dark:` de Tailwind. */
export const DARK_CLASS = "dark";

const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

/**
 * Runs synchronously in `<head>`, before the first paint, so a user who picked
 * dark never sees a white flash. The server cannot render the right theme —
 * the choice lives in `localStorage`, which does not exist there — so the
 * correction has to happen while the browser is still parsing the HTML. A
 * `useEffect` would run after paint, which is exactly the flash.
 * See `node_modules/next/dist/docs/01-app/02-guides/preventing-flash-before-hydration.md`.
 *
 * || Corre sincrónico en `<head>`, antes del primer pintado, para que quien
 * eligió oscuro no vea un flash blanco. El servidor no puede renderizar el
 * tema correcto —la elección vive en `localStorage`, que ahí no existe—, así
 * que la corrección tiene que pasar mientras el browser todavía parsea el
 * HTML. Un `useEffect` correría después del pintado: eso es justamente el flash.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var s=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)});var d=s?s===${JSON.stringify(
  "dark",
)}:window.matchMedia(${JSON.stringify(
  DARK_MEDIA_QUERY,
)}).matches;document.documentElement.classList.toggle(${JSON.stringify(
  DARK_CLASS,
)},d)}catch(e){}})()`;

/**
 * The explicit choice, or `null` when the user never made one and the system
 * preference still rules. Returns `null` too when storage is unavailable
 * (private mode, blocked cookies): a theme is not worth throwing over.
 *
 * || La elección explícita, o `null` cuando el usuario nunca eligió y manda la
 * preferencia del sistema. También devuelve `null` si el storage no está
 * disponible (modo privado, cookies bloqueadas): un tema no amerita un throw.
 */
export function readStoredTheme(): Theme | null {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  } catch {
    return null;
  }
}

/** What the OS asks for right now. || Lo que pide el sistema operativo ahora. */
export function systemTheme(): Theme {
  return window.matchMedia(DARK_MEDIA_QUERY).matches ? "dark" : "light";
}

/** The theme in effect: the explicit choice if there is one, else the system's.
 *  || El tema vigente: la elección explícita si la hay, si no la del sistema. */
export function resolveTheme(): Theme {
  return readStoredTheme() ?? systemTheme();
}

/** Paints a theme. Does not persist it — see `storeTheme`.
 *  Uses `classList` on `<html>`; that element must NOT expose `className` in
 *  the root layout JSX or React hydration will reset the attribute.
 *  || Pinta un tema. No lo persiste — ver `storeTheme`. Usa `classList` en
 *  `<html>`; ese elemento no debe tener `className` en el JSX del layout raíz
 *  o la hidratación de React resetea el atributo. */
export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle(DARK_CLASS, theme === "dark");
}

/** Persists the explicit choice, so it survives a reload and beats the system.
 *  || Persiste la elección explícita, para que sobreviva un reload y le gane al sistema. */
export function storeTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Storage unavailable: the theme still applies for this page.
    // || Storage no disponible: el tema igual aplica en esta página.
  }
}

/**
 * Calls back when the OS preference changes, but only matters while no explicit
 * choice is stored — an explicit choice wins over the system, always.
 *
 * || Avisa cuando cambia la preferencia del sistema, pero solo importa mientras
 * no haya elección explícita guardada — una elección explícita le gana al
 * sistema, siempre.
 */
export function watchSystemTheme(onChange: (theme: Theme) => void): () => void {
  const query = window.matchMedia(DARK_MEDIA_QUERY);
  const handler = (event: MediaQueryListEvent) =>
    onChange(event.matches ? "dark" : "light");
  query.addEventListener("change", handler);
  return () => query.removeEventListener("change", handler);
}
