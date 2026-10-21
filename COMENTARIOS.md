# Comentarios, cuentas con Google y avisos de precio

## Qué hace
- **Comentarios en cada ficha** (`/notebook/...`, `/celular/...`, etc.). Para comentar hay que iniciar sesión con Google;
  para mirar precios no hace falta cuenta. Se muestra el nombre (nombre e inicial del apellido) y la foto de Google. El correo no se publica.
- **Los comentarios no se pierden**: se guardan con la dirección fija de la ficha (`herramientas/fichas.json`).
  Si un equipo se agota, su ficha y sus comentarios siguen. Si sale de las listas y vuelve a subirse con otro id,
  `herramientas/fichas.py` le devuelve la misma dirección, con sus comentarios y los avisos que la gente pidió.
- **"Avísame si baja de precio"** (o "cuando vuelva a tener stock") bajo el precio de cada ficha.
  Avisamos cuando baja al menos 2% y $2.000 desde el precio que vio la persona. Un correo por persona y por día, con todos sus equipos.
- **Resumen diario** (opcional, la persona lo acepta): las mayores bajadas del día (al menos 3% y $3.000). Solo sale los días que hay bajadas.
- **Mi cuenta** (`/mi-cuenta`): equipos que sigue, activar o quitar el resumen, cerrar sesión y borrar la cuenta con sus comentarios.
- **Panel** (`/panel`): números, moderar comentarios (ocultar, borrar, bloquear personas), descargar la base de correos para Excel
  y ver el estado del envío. Solo entra `adictosdigitalesla@gmail.com` y las cuentas de la variable `ADMIN_CORREOS`.
- Cada correo trae un enlace para darse de baja con un clic (y la cabecera List-Unsubscribe que piden Gmail y Outlook).

## Cómo funciona por dentro
- `functions/_comun.js`: base de datos (las tablas se crean solas), sesión con cookie firmada, verificación del token de Google, envío de correos.
- `functions/api/sesion.js`, `comentarios.js`, `avisos.js`, `cuenta.js`, `panel.js`, `baja.js`, `revisar-avisos.js`.
- `assets/comentarios.js`: la sección de comentarios, el botón "Avísame", la ventana para iniciar sesión y la página Mi cuenta. `assets/panel.js`: el panel.
- `herramientas/fichas.py` escribe `assets/avisos.json` (precio de hoy de cada ficha y bajadas del día).
- `.github/workflows/avisos.yml`: cuando termina "Fotos y fichas", espera que Cloudflare publique y llama a `/api/revisar-avisos`,
  que arma los avisos y los envía de a 25 por llamada. Si los precios no cambiaron, no hace nada.

## Configuración en Cloudflare (Pages → cualmeconviene → Settings)
1. **Bindings**: base D1 `cualmeconviene-clics` con el nombre `DB` (la misma del contador de clics).
2. **Variables and secrets**:
   - `GOOGLE_CLIENT_ID` (texto): el ID de cliente web de Google (termina en `.apps.googleusercontent.com`). También se puede escribir en `functions/_comun.js`.
   - `BREVO_API_KEY` (secreto): clave de API de Brevo (300 correos diarios gratis). En su lugar puede ir `RESEND_API_KEY` (100 diarios gratis).
   - `CORREO_REMITENTE` (opcional): por defecto `avisos@cualmeconviene.cl` (el dominio debe estar verificado en Brevo).
   - `ADMIN_CORREOS` (opcional): otras cuentas de Google que pueden entrar al panel, separadas por coma.
3. Volver a desplegar para que tome los cambios.

Mientras no exista `GOOGLE_CLIENT_ID`, la sección de comentarios y el botón "Avísame" no se muestran.
Mientras no exista la clave de correo, los avisos quedan guardados y se envían cuando se configure.

## Google (console.cloud.google.com, una sola vez)
1. Crear un proyecto "Cual me conviene".
2. APIs y servicios → Pantalla de consentimiento de OAuth: tipo Externo, nombre "¿Cuál me conviene?", correo de asistencia
   adictosdigitalesla@gmail.com, dominio autorizado `cualmeconviene.cl`, enlace a la política `https://cualmeconviene.cl/#privacidad`.
   Permisos: solo los básicos (correo, perfil, openid). Publicar la app ("En producción"): con permisos básicos no requiere revisión de Google.
3. Credenciales → Crear ID de cliente de OAuth → Aplicación web. Orígenes de JavaScript autorizados:
   `https://cualmeconviene.cl` y `https://www.cualmeconviene.cl`. No hace falta URI de redirección.
4. Copiar el ID de cliente y ponerlo en `GOOGLE_CLIENT_ID`.

## Consultas útiles (consola de D1)
```sql
-- Personas que aceptaron el resumen diario
SELECT correo, nombre, creado FROM usuarios WHERE resumen = 1 ORDER BY creado DESC;
-- Equipos más seguidos
SELECT producto, COUNT(*) AS personas FROM avisos GROUP BY producto ORDER BY personas DESC LIMIT 20;
-- Comentarios de un equipo
SELECT c.creado, u.nombre, c.texto, c.oculto FROM comentarios c JOIN usuarios u ON u.id = c.usuario
WHERE c.producto = 'notebook/acer-aspire-14-a14-52mt-59pe' ORDER BY c.id DESC;
-- Correos que fallaron
SELECT creado, para, asunto, error FROM correos WHERE enviado = 'fallido' ORDER BY id DESC LIMIT 20;
```
