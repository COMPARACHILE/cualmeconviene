# Contador de clics a tiendas

Cada vez que alguien toca el precio de un equipo en una tienda, la página envía a `/api/clic`
solo el id del equipo, la tienda y el nombre del equipo. La función `functions/api/clic.js`
suma 1 en la base D1, agrupado por día (hora de Chile), equipo y tienda.
No se guardan cookies, IP ni datos de la persona.

## Configuración en Cloudflare (una sola vez)
1. Crear una base D1 (Storage & databases → D1) y ejecutar `schema.sql` en su consola.
2. En el proyecto de Pages → Settings → Bindings, agregar la base D1 con el nombre de variable `DB`
   (en Production y en Preview).
3. Volver a desplegar para que la función vea la base.

Si la base no está enlazada, la función responde sin guardar nada y la página sigue funcionando.

## Consultas útiles (consola de D1)

```sql
-- Equipos más clickeados en los últimos 7 días
SELECT nombre, SUM(n) AS clics FROM clics WHERE dia >= date('now','-7 days') GROUP BY equipo ORDER BY clics DESC LIMIT 20;

-- Clics por tienda
SELECT tienda, SUM(n) AS clics FROM clics GROUP BY tienda ORDER BY clics DESC;

-- Clics por día
SELECT dia, SUM(n) AS clics FROM clics GROUP BY dia ORDER BY dia DESC;
```

# Opiniones de las personas (botón "¿Qué te parece?")

El botón flotante de abajo a la derecha envía a `/api/opinion` el voto (me gustó / no me convenció),
el comentario y la página. Se guarda en la misma base D1, tabla `opiniones`. No se guardan IP ni cookies.

**Activar (una sola vez):** en la consola de D1, ejecuta el bloque `CREATE TABLE IF NOT EXISTS opiniones …` de `schema.sql`.

```sql
-- Últimas opiniones
SELECT dia, pagina, CASE voto WHEN 1 THEN '👍' WHEN -1 THEN '👎' ELSE '' END AS voto, texto
FROM opiniones ORDER BY id DESC LIMIT 50;

-- Balance de me gusta / no me convence
SELECT SUM(voto = 1) AS me_gusto, SUM(voto = -1) AS no_convencio, COUNT(*) AS total FROM opiniones;
```
