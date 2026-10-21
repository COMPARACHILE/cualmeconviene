-- Tabla del contador de clics (se crea una sola vez en la base D1)
CREATE TABLE IF NOT EXISTS clics (
  dia    TEXT    NOT NULL,           -- AAAA-MM-DD, hora de Chile
  equipo TEXT    NOT NULL,           -- id del equipo en la página (ej. g12)
  tienda TEXT    NOT NULL,           -- falabella, paris, ripley o pcfactory
  nombre TEXT    NOT NULL DEFAULT '', -- nombre del equipo, para leer los reportes
  n      INTEGER NOT NULL DEFAULT 0,  -- cantidad de clics ese día
  PRIMARY KEY (dia, equipo, tienda)
);

-- Opiniones del botón "¿Qué te parece?" (se crea una sola vez en la misma base D1)
CREATE TABLE IF NOT EXISTS opiniones (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  dia    TEXT    NOT NULL,            -- AAAA-MM-DD, hora de Chile
  pagina TEXT    NOT NULL,            -- /, /notebooks o /celulares
  voto   INTEGER NOT NULL DEFAULT 0,  -- 1 me gustó, -1 no me convenció, 0 sin voto
  texto  TEXT    NOT NULL DEFAULT ''  -- qué mejorarían o agregarían
);

-- Cuentas, comentarios y avisos de precio: las funciones las crean solas (ver functions/_comun.js y COMENTARIOS.md).
-- Se dejan aquí como referencia para consultas en la consola de D1.
CREATE TABLE IF NOT EXISTS usuarios (
  id TEXT PRIMARY KEY, google TEXT NOT NULL UNIQUE, correo TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '',
  foto TEXT NOT NULL DEFAULT '', creado TEXT NOT NULL, ultimo TEXT NOT NULL,
  resumen INTEGER NOT NULL DEFAULT 0,          -- 1 = aceptó el resumen diario de bajadas
  consentimiento TEXT NOT NULL DEFAULT '',     -- qué eligió y cuándo
  bloqueado INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS comentarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  producto TEXT NOT NULL,                      -- dirección fija de la ficha, ej. notebook/acer-aspire-14
  usuario TEXT NOT NULL, texto TEXT NOT NULL, creado TEXT NOT NULL, oculto INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS avisos (
  usuario TEXT NOT NULL, producto TEXT NOT NULL, nombre TEXT NOT NULL DEFAULT '',
  precio INTEGER,                              -- avisamos si baja de este precio
  stock INTEGER NOT NULL DEFAULT 1, creado TEXT NOT NULL, avisado TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (usuario, producto));
CREATE TABLE IF NOT EXISTS correos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL, para TEXT NOT NULL, tipo TEXT NOT NULL,
  asunto TEXT NOT NULL, html TEXT NOT NULL, texto TEXT NOT NULL, baja TEXT NOT NULL DEFAULT '',
  creado TEXT NOT NULL, enviado TEXT NOT NULL DEFAULT '', intentos INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
