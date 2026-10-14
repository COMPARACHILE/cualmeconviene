-- Tabla del contador de clics (se crea una sola vez en la base D1)
CREATE TABLE IF NOT EXISTS clics (
  dia    TEXT    NOT NULL,           -- AAAA-MM-DD, hora de Chile
  equipo TEXT    NOT NULL,           -- id del equipo en la página (ej. g12)
  tienda TEXT    NOT NULL,           -- falabella, paris, ripley o pcfactory
  nombre TEXT    NOT NULL DEFAULT '', -- nombre del equipo, para leer los reportes
  n      INTEGER NOT NULL DEFAULT 0,  -- cantidad de clics ese día
  PRIMARY KEY (dia, equipo, tienda)
);
