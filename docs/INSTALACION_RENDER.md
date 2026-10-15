# Instalación de MalaboMarket en Render

Cada comprador del software tiene **su propio** servicio, base de datos y dominio. Estos pasos se repiten por cliente.

## 1. Antes de empezar
- Cuenta en [Render](https://render.com) y el código en un repositorio de GitHub (privado).
- Un bucket para las fotos compatible con S3 (Cloudflare R2 recomendado: tiene plan gratuito generoso). Apunta: Access Key, Secret Key, nombre del bucket y endpoint.
- Un dominio (opcional al principio; Render da uno `*.onrender.com`).

## 2. Crear los servicios
1. En Render: **New → Blueprint** y elige el repositorio. Render lee `render.yaml` y crea la base de datos PostgreSQL, el servicio web y la tarea diaria que expira anuncios.
2. Rellena las variables que pide (las marcadas `sync: false`):

| Variable | Qué poner |
|---|---|
| `DJANGO_ALLOWED_HOSTS` | `tudominio.com,malabomarket-web.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://tudominio.com,https://malabomarket-web.onrender.com` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` | Datos del bucket |
| `AWS_S3_CUSTOM_DOMAIN` | (opcional) dominio público del bucket para las fotos |
| `SITE_NAME_FIRST`, `SITE_NAME_SECOND` | Nombre de la marca en dos partes (p. ej. `Malabo` y `Market`) |
| `SITE_PHONE`, `SITE_WHATSAPP`, `SITE_EMAIL`, `SITE_LOCATION`, `SITE_TAGLINE` | Datos de contacto del cliente |
| `SITE_COLOR_PRIMARY`, `SITE_COLOR_ACCENT` | Colores en hex, p. ej. `#0B3954` |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Servidor de correo (Resend, Brevo, etc.) |

`DJANGO_SECRET_KEY` y `DATABASE_URL` los pone Render solo.

3. Cada despliegue ejecuta `migrate` automáticamente (`preDeployCommand`) y vigila `/salud/`.

## 3. Primer acceso
En el servicio web → **Shell**:
```
python manage.py createsuperuser
```
Entra en `/admin/`, crea las ciudades (Malabo, Bata…) y ajusta los **Planes** (precio y duración). Para dar acceso al personal de la oficina, crea sus usuarios y cambia el rol a *personal de oficina*.

## 4. Dominio propio
Servicio web → **Settings → Custom Domains**. Añade el dominio, crea el registro DNS que indica Render y añádelo también a `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`. El HTTPS es automático.

## 5. Actualizar el diseño (solo si cambias clases de Tailwind)
El CSS ya viene compilado en `static/css/tailwind.css`. Si modificas plantillas y añades clases nuevas:
```
npm install
npm run build:css
```
y sube el archivo resultante al repositorio.

## 6. Comprobaciones tras el despliegue
- `https://tudominio.com/salud/` responde `ok`.
- Se puede registrar un usuario, publicar un anuncio gratuito y verlo en la portada.
- En `/oficina/` se registra un cobro y se imprime el recibo.
- Las fotos se cargan desde el bucket.
