-- Esquema ajeno a XEON (mismo modelo que la prueba SQLite). Solo para pruebas.
CREATE TABLE articulos (
    codigo VARCHAR(40) PRIMARY KEY, titulo VARCHAR(200) NOT NULL, unidad_venta VARCHAR(20) NOT NULL,
    precio_centavos BIGINT NOT NULL, alias_texto VARCHAR(200));
CREATE TABLE sucursales (clave VARCHAR(40) PRIMARY KEY, rotulo VARCHAR(200) NOT NULL, apodos VARCHAR(200));
CREATE TABLE existencias (
    codigo_articulo VARCHAR(40) NOT NULL, bodega VARCHAR(40) NOT NULL, disponibles DECIMAL(12,3) NOT NULL,
    actualizado DATETIME NOT NULL, vigente_hasta DATETIME);

INSERT INTO articulos VALUES
  ('FER-01', 'Cemento Ferreteria Robles', 'SAC', 3755000, 'cemento'),
  ('FER-02', 'Pala redonda Robles', 'UND', 4370000, 'pala');
INSERT INTO sucursales VALUES ('BOD-7', 'Ferreteria Robles Principal', 'Robles|principal');
INSERT INTO existencias VALUES
  ('FER-01', 'BOD-7', 12, UTC_TIMESTAMP(), UTC_TIMESTAMP() + INTERVAL 2 HOUR),
  ('FER-02', 'BOD-7', 4.5, UTC_TIMESTAMP(), UTC_TIMESTAMP() + INTERVAL 2 HOUR);

CREATE USER 'tienda_ro'@'%' IDENTIFIED BY 'solo-prueba-lectura';
GRANT SELECT ON tienda.* TO 'tienda_ro'@'%';
