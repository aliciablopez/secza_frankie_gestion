-- ============================================================
--  ESQUEMA RELACIONAL FRANKIE GESTOR (Fuente Maestra - SQLite)
-- ============================================================

-- Habilitamos la validación estricta de llaves foráneas (fundamental en SQLite).
PRAGMA foreign_keys = ON;

-- 1. TABLA ROLES
-- Define los niveles de jerarquía del sistema.
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT
);

-- 2. TABLA USUARIOS
-- Gestiona las credenciales de acceso al sistema (autenticación).
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1
);

-- 3. TABLA USUARIOS_ROLES (Tabla Intermedia)
-- Permite que un usuario tenga múltiples roles (Relación Muchos a Muchos).
CREATE TABLE IF NOT EXISTS usuarios_roles (
    id_usuario INTEGER NOT NULL,
    id_rol INTEGER NOT NULL,
    PRIMARY KEY (id_usuario, id_rol),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (id_rol) REFERENCES roles(id) ON DELETE CASCADE
);

-- 4. TABLA PERSONAS (Tabla Base / Superclase)
-- Centraliza los datos de contacto. Empleados, Clientes y Proveedores heredan de esta.
CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_persona TEXT NOT NULL, -- 'Fisica' o 'Juridica'
    nombres TEXT,
    apellidos TEXT,
    razon_social TEXT,
    tipo_documento TEXT NOT NULL, -- 'DNI', 'CUIT', 'CUIL', 'Pasaporte'
    nro_documento TEXT NOT NULL UNIQUE,
    telefono TEXT,
    email TEXT,
    domicilio TEXT,
    ciudad TEXT,
    provincia TEXT,
    codigo_postal TEXT,

    CONSTRAINT chk_tipo_persona CHECK (
        (tipo_persona = 'Fisica' AND nombres IS NOT NULL AND apellidos IS NOT NULL AND razon_social IS NULL) OR
        (tipo_persona = 'Juridica' AND razon_social IS NOT NULL AND nombres IS NULL AND apellidos IS NULL)
    ),
    CONSTRAINT chk_tipo_doc CHECK (
        tipo_documento IN ('DNI', 'CUIT', 'CUIL', 'Pasaporte')
    )
);

-- 5. TABLA CLIENTES
-- Hereda de 'personas' mediante 'id_persona'.
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    fecha_alta DATE DEFAULT CURRENT_DATE,
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);

-- 6. TABLA PROVEEDORES
-- Hereda de 'personas' e incluye 'activo' para la baja lógica.
CREATE TABLE IF NOT EXISTS proveedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    rubro TEXT,
    contacto_secundario TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE
);

-- 7. TABLA EMPLEADOS
-- Hereda de 'personas' y se vincula opcionalmente con 'usuarios'.
CREATE TABLE IF NOT EXISTS empleados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_persona INTEGER NOT NULL UNIQUE,
    id_usuario INTEGER UNIQUE,
    legajo TEXT NOT NULL UNIQUE,
    cargo TEXT NOT NULL CHECK (
        cargo IN ('Gerente', 'Administrativo', 'Admin', 'Vendedor')
    ),
    sector TEXT NOT NULL CHECK (
        sector IN ('Gestión', 'Staff', 'Ventas', 'Compras', 'Administración')
    ),
    tipo_vinculo TEXT NOT NULL CHECK (
        tipo_vinculo IN ('Propietario', 'Contratado', 'Pasante', 'Permanente')
    ),
    sueldo REAL NOT NULL CHECK (sueldo >= 0),
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_persona) REFERENCES personas(id) ON DELETE CASCADE,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- 8. TABLA PRODUCTOS
-- Inventario. Clave foránea restrictiva para no borrar proveedores con productos asignados.
CREATE TABLE IF NOT EXISTS productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    categoria TEXT,
    id_proveedor INTEGER NOT NULL,
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 5 CHECK (stock_minimo >= 0),
    precio_costo REAL NOT NULL DEFAULT 0.0 CHECK (precio_costo >= 0),
    precio_venta REAL NOT NULL DEFAULT 0.0 CHECK (precio_venta >= 0),
    ubicacion TEXT,
    vencimiento DATE,
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id) ON DELETE RESTRICT
);

-- 9. TABLA FACTURAS (Cabecera)
CREATE TABLE IF NOT EXISTS facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    id_cliente INTEGER NOT NULL,
    id_vendedor INTEGER NOT NULL,
    total REAL NOT NULL DEFAULT 0.00,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id) ON DELETE RESTRICT,
    FOREIGN KEY (id_vendedor) REFERENCES empleados(id) ON DELETE RESTRICT
);

-- 10. TABLA FACTURAS_DETALLES (Cuerpo)
CREATE TABLE IF NOT EXISTS facturas_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_factura INTEGER NOT NULL,
    id_producto INTEGER NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    descuento_porcentaje REAL NOT NULL DEFAULT 0.00,
    subtotal REAL NOT NULL DEFAULT 0.00,
    FOREIGN KEY (id_factura) REFERENCES facturas(id) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos(id) ON DELETE RESTRICT
);

-- 11. TABLA LIQUIDACIONES_HABERES (Nómina de sueldos e historial remunerativo)
CREATE TABLE IF NOT EXISTS liquidaciones_haberes (
    id_liquidacion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empleado INTEGER NOT NULL,
    periodo TEXT NOT NULL,
    sueldo_basico REAL NOT NULL,
    total_remunerativo REAL NOT NULL,
    total_no_remunerativo REAL NOT NULL DEFAULT 0.00,
    total_descuentos REAL NOT NULL,
    neto_a_cobrar REAL NOT NULL,
    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id_empleado, periodo),
    FOREIGN KEY (id_empleado) REFERENCES empleados(id) ON DELETE CASCADE
);


-- ==========================================================
--  TRIGGERS (Integridad y Automatización en SQLite)
-- ==========================================================

-- 1. Valida disponibilidad de stock ANTES de insertar el detalle.
CREATE TRIGGER IF NOT EXISTS trg_validar_stock
BEFORE INSERT ON facturas_detalles
FOR EACH ROW
WHEN (SELECT stock_actual FROM productos WHERE id = NEW.id_producto) < NEW.cantidad
BEGIN
    SELECT RAISE(ABORT, 'Transacción Abortada: Stock Insuficiente para el producto.');
END;

-- 2. Calcula el subtotal de la línea DESPUÉS de insertar si no vino informado.
CREATE TRIGGER IF NOT EXISTS trg_calcular_subtotal
AFTER INSERT ON facturas_detalles
FOR EACH ROW
WHEN NEW.subtotal = 0
BEGIN
    UPDATE facturas_detalles
    SET subtotal = ROUND((NEW.cantidad * NEW.precio_unitario) * (1.0 - (NEW.descuento_porcentaje / 100.0)), 2)
    WHERE id = NEW.id;
END;

-- 3. Descuenta el stock físico DESPUÉS de insertar el detalle.
CREATE TRIGGER IF NOT EXISTS trg_descontar_stock
AFTER INSERT ON facturas_detalles
FOR EACH ROW
BEGIN
    UPDATE productos
    SET stock_actual = stock_actual - NEW.cantidad
    WHERE id = NEW.id_producto;
END;

-- 4. Acumula el subtotal de la línea en la cabecera de la factura.
CREATE TRIGGER IF NOT EXISTS trg_sumar_total_factura
AFTER INSERT ON facturas_detalles
FOR EACH ROW
BEGIN
    UPDATE facturas
    SET total = ROUND(total + NEW.subtotal, 2)
    WHERE id = NEW.id_factura;
END;


-- ==========================================================
--  SEMILLAS INICIALES
-- ==========================================================
INSERT OR IGNORE INTO roles (nombre, descripcion) VALUES
('Administrador', 'Control total del sistema'),
('Gerente', 'Gestión operativa sin acceso a roles superiores'),
('Empleado - Ventas', 'Acceso a clientes y facturación'),
('Empleado - Compras', 'Acceso a proveedores y stock');

INSERT OR IGNORE INTO usuarios (username, password, activo) VALUES
('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 1);

INSERT OR IGNORE INTO usuarios_roles (id_usuario, id_rol) VALUES (1, 1);