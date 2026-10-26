-- Esquema ajeno a XEON (mismo modelo que la prueba SQLite). Solo para pruebas.
CREATE TABLE articulos (
    codigo text PRIMARY KEY, titulo text NOT NULL, unidad_venta text NOT NULL,
    precio_centavos bigint NOT NULL, alias_texto text);
CREATE TABLE sucursales (clave text PRIMARY KEY, rotulo text NOT NULL, apodos text);
CREATE TABLE existencias (
    codigo_articulo text NOT NULL, bodega text NOT NULL, disponibles numeric(12,3) NOT NULL,
    actualizado timestamptz NOT NULL, vigente_hasta timestamptz);

INSERT INTO articulos VALUES
  ('FER-01', 'Cemento Ferreteria Robles', 'SAC', 3755000, 'cemento'),
  ('FER-02', 'Pala redonda Robles', 'UND', 4370000, 'pala');
INSERT INTO sucursales VALUES ('BOD-7', 'Ferreteria Robles Principal', 'Robles|principal');
INSERT INTO existencias VALUES
  ('FER-01', 'BOD-7', 12, now(), now() + interval '2 hours'),
  ('FER-02', 'BOD-7', 4.5, now(), now() + interval '2 hours');

CREATE ROLE tienda_ro LOGIN PASSWORD 'solo-prueba-lectura';
GRANT CONNECT ON DATABASE tienda TO tienda_ro;
GRANT USAGE ON SCHEMA public TO tienda_ro;
GRANT SELECT ON articulos, sucursales, existencias TO tienda_ro;
