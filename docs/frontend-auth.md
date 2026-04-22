# Integración de autenticación con el frontend

Guía para consumir la API de `erp-backend` desde el frontend (Next.js 16 / React).

---

## Resumen del modelo

- El backend emite **dos cookies `HttpOnly`** al hacer login: `access_token` (15 min) y `refresh_token` (7 días). El navegador las adjunta automáticamente a cada request al mismo origen.
- El JavaScript del frontend **no puede leer** esas cookies (por diseño). Tampoco le hace falta: el backend valida la sesión en cada request.
- El JWT tiene payload **mínimo**: `sub`, `jti`, `type`, `mfa_verified`, `exp`. **No** incluye `role` ni `tenant_id`.
- Para saber quién es el usuario (rol, tenant, nombre del estudio, etc.), el front llama **`GET /api/v1/auth/me`** y guarda la respuesta en un store de cliente.

> **Regla de oro**: el rol en el cliente es solo para UX (mostrar/ocultar botones). El backend revalida cada operación contra la DB y devuelve 403 si el usuario no tiene permiso. Nunca confíes en el rol del store para enforzar seguridad.

---

## Flujo completo

```
┌──────────┐    POST /auth/login      ┌──────────┐
│  front   │ ───────────────────────▶ │ backend  │
│          │ ◀─────────── Set-Cookie: access_token + refresh_token (HttpOnly)
│          │                          └──────────┘
│          │
│          │    GET /auth/me (cookie automática)
│          │ ───────────────────────▶ backend
│          │ ◀── { user_id, email, role, tenant_id, studio_slug, ... }
│          │
│          │   guardar en store global → UI reactiva
└──────────┘
```

---

## 1. Cliente HTTP base

```ts
// lib/api.ts
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request(path: string, init: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include", // envía/recibe cookies cross-origin si aplica
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  return res;
}

export const api = {
  login: (email: string, password: string) =>
    request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request("/api/v1/auth/logout", { method: "POST" }),
  me: () => request("/api/v1/auth/me"),
};
```

Si el front y el back están en el **mismo origen** (ej. `/api` proxyado por Next), omite `credentials: "include"` — el navegador manda cookies automáticamente.

---

## 2. Tipos del usuario

```ts
// types/auth.ts
export type Role = "OWNER" | "ADMIN" | "MONITOR" | "MODEL";

export interface Me {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  mfa_enabled: boolean;
  tenant_id: string;
  studio_slug: string;
}
```

---

## 3. Store de sesión (Zustand)

```ts
// stores/auth.ts
import { create } from "zustand";
import { api } from "@/lib/api";
import type { Me } from "@/types/auth";

interface AuthState {
  me: Me | null;
  status: "idle" | "loading" | "authed" | "guest";
  refresh: () => Promise<void>;
  clear: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  me: null,
  status: "idle",
  refresh: async () => {
    set({ status: "loading" });
    const res = await api.me();
    if (res.ok) {
      set({ me: await res.json(), status: "authed" });
    } else {
      set({ me: null, status: "guest" });
    }
  },
  clear: () => set({ me: null, status: "guest" }),
}));
```

Equivalente con Context/Redux/Jotai: misma idea, distinto boilerplate.

---

## 4. Bootstrap en el layout raíz

```tsx
// app/providers.tsx
"use client";
import { useEffect } from "react";
import { useAuth } from "@/stores/auth";

export function AuthBootstrap({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    useAuth.getState().refresh();
  }, []);
  return <>{children}</>;
}
```

Montá `<AuthBootstrap>` una sola vez en `app/layout.tsx`.

---

## 5. Uso en componentes (UX únicamente)

```tsx
import { useAuth } from "@/stores/auth";

export function Sidebar() {
  const { me } = useAuth();
  if (!me) return null;

  return (
    <nav>
      {me.role === "OWNER" && <Link href="/settings/users">Usuarios</Link>}
      {(["OWNER", "ADMIN"] as const).includes(me.role) && (
        <Link href="/rooms">Salas</Link>
      )}
      {me.role === "MONITOR" && <Link href="/monitor/dashboard">Turnos</Link>}
      {me.role === "MODEL" && <Link href="/model/dashboard">Mis métricas</Link>}
    </nav>
  );
}
```

Hook helper para chequeo de rol:

```ts
// hooks/useRole.ts
import { useAuth } from "@/stores/auth";
import type { Role } from "@/types/auth";

export function useHasRole(...allowed: Role[]): boolean {
  const role = useAuth((s) => s.me?.role);
  return role !== undefined && allowed.includes(role);
}
```

```tsx
const isStaff = useHasRole("OWNER", "ADMIN");
{isStaff && <AdminPanel />}
```

---

## 6. Cuándo refrescar `/me`

| Evento                          | Acción                             |
|---------------------------------|------------------------------------|
| Arranque de la app (layout root)| `refresh()`                        |
| Login exitoso                   | `refresh()`                        |
| Tras `POST /auth/mfa/verify`    | `refresh()` (cambia `mfa_enabled`) |
| Respuesta 401 en cualquier call | `clear()` + redirigir a `/login`   |
| Logout                          | `POST /auth/logout` → `clear()`    |
| Cambio de rol externo sospechado| `refresh()` o polling cada N min   |

---

## 7. Interceptor de 401 para redirigir

```ts
// lib/api.ts (extensión)
import { useAuth } from "@/stores/auth";

export async function api2<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await request(path, init);
  if (res.status === 401) {
    useAuth.getState().clear();
    window.location.href = "/login";
    throw new Error("unauthenticated");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

---

## 8. Protección de rutas en Next.js

### Cliente (redirect tardío pero simple)

```tsx
// app/(protected)/layout.tsx
"use client";
import { useAuth } from "@/stores/auth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "guest") router.replace("/login");
  }, [status, router]);

  if (status === "loading" || status === "idle") return <Spinner />;
  return <>{children}</>;
}
```

### Middleware (chequeo barato, sin decodificar JWT)

```ts
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED = ["/dashboard", "/rooms", "/users"];

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;
  if (!PROTECTED.some((p) => path.startsWith(p))) return NextResponse.next();
  if (!req.cookies.get("access_token")) {
    return NextResponse.redirect(new URL("/login", req.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next|api|favicon.ico).*)"],
};
```

Importante: el middleware **solo chequea presencia de cookie**, no la valida. La validación real ocurre en el backend en cada request.

### Server component (SSR con rol)

```tsx
// app/(protected)/owner-only/page.tsx
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function getMe() {
  const jar = cookies();
  const res = await fetch(`${process.env.API_URL}/api/v1/auth/me`, {
    headers: { cookie: jar.toString() },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function OwnerOnlyPage() {
  const me = await getMe();
  if (!me) redirect("/login");
  if (me.role !== "OWNER") redirect("/403");
  return <OwnerDashboard me={me} />;
}
```

---

## 9. Refresh automático del access token

El `access_token` vive 15 min, el `refresh_token` 7 días. Cuando un request devuelva 401 por expiración, el front puede:

1. Llamar `POST /auth/refresh` (usa la cookie `refresh_token` automáticamente).
2. Si devuelve 200, reintentar el request original.
3. Si devuelve 401, hacer `clear()` + redirect.

```ts
async function withRefresh<T>(req: () => Promise<Response>): Promise<T> {
  let res = await req();
  if (res.status === 401) {
    const r = await fetch(`${API}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!r.ok) {
      useAuth.getState().clear();
      window.location.href = "/login";
      throw new Error("session expired");
    }
    res = await req();
  }
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<T>;
}
```

---

## 10. CORS y cookies cross-origin

Si el front corre en otro origen (ej. `https://app.example.com` y la API en `https://api.example.com`):

- Backend: `CORS_ORIGINS` debe incluir el origen exacto del front. No usar `*` con credenciales (el backend ya lo impide).
- Backend: `SESSION_COOKIE_SECURE=true` en prod — las cookies solo viajan por HTTPS.
- Frontend: todas las llamadas `fetch` necesitan `credentials: "include"`.
- Mismo sitio registrable: ambos dominios deben ser *same-site* para que `SameSite=Lax` funcione. Para cross-site habría que pasar a `SameSite=None; Secure`, lo cual se puede configurar extendiendo `_COOKIE_OPTS` en `app/api/v1/auth.py` si hace falta.

---

## 11. Logout correcto

```ts
async function logout() {
  await api.logout();           // blacklistea tokens en Redis
  useAuth.getState().clear();   // limpia el store
  // cookies se limpian del navegador por Set-Cookie vacío que manda el backend
  window.location.href = "/login";
}
```

---

## Referencias

- [`app/api/v1/auth.py`](../app/api/v1/auth.py) — implementación de los endpoints.
- [`app/services/auth.py`](../app/services/auth.py) — reglas de negocio, blacklist, MFA.
- [`app/core/dependencies.py`](../app/core/dependencies.py) — `CurrentUser`, `require_roles`, `MFAVerifiedUser`.
- [`tests/api/test_me_endpoint.py`](../tests/api/test_me_endpoint.py) — contrato de `/me` y garantía de JWT mínimo.
