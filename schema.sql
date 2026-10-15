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
