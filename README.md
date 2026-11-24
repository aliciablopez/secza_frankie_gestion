# Frankie - Sistema de Gestión Comercial

Sistema de escritorio integral desarrollado en Python bajo los principios de Clean Architecture, diseñado para automatizar y optimizar la administración comercial, control de inventario, padrón de clientes y proveedores, facturación y gestión de recursos humanos en PyMEs.
Este proyecto es un fork de un trabajo grupal: https://github.com/CFP-Nro-404-Curso-Python/FRANKIE_GESTOR_GRUPAL.git


## Características Principales

### 1. Inventario y Control de Stock

- **Stock Mínimo Configurable:** Valor por defecto de 75 unidades por producto.
    
- **Alertas de Reposición:** Detección automática de artículos con stock crítico ($\le 75$ unidades o por debajo del stock mínimo estipulado).
    
- **Cálculo de Precios:** Margen sugerido sobre el precio de costo para la determinación del precio de venta.
    
- **Emisión de Órdenes de Compra:** Generación de comprobante y registro de Orden de Compra (OC) para productos en o por debajo del stock mínimo.
    
- **Gestión de Productos:** Alta, modificación, búsqueda con filtros, alerta de stock bajo y baja lógica (desactivación/reactivación).
    
### 2. Gestión de Proveedores y Clientes

- **Padrón Comercial:** Registro completo de personas físicas y jurídicas (CUIT, razón social, rubro, datos de contacto y domicilio).
    
- **Baja Lógica:** Desactivación y reactivación segura de registros garantizando la integridad referencial histórica.
    
### 3. Recursos Humanos (Empleados y Haberes)

- **Padrón de Personal:** Registro y actualización de legajos de empleados.
    
- **Liquidación de Haberes:** Cálculo de sueldos y control de recibos asociados.
    
### 4. Facturación y Ventas

- **Emisión de Comprobantes:** Módulo de ventas integrado al stock en tiempo real.
    
### 5. Interfaz Gráfica y Seguridad

- **Diseño Apilado Estandarizado:** Formulario en la sección superior y grilla/tabla en la sección inferior.
    
- **Estilos Unificados:** Hoja de estilos compartida, tipografía sin cursivas en 12 pt para máxima legibilidad.
    
- **Control de Accesos (RBAC):** Restricción de acciones de escritura según el rol activo del usuario (por ejemplo, perfil administrador o gerente).
    
## Arquitectura y Estructura del Proyecto

El proyecto sigue una organización modular guiada por Clean Architecture:

- `main.py`: Punto de entrada de la aplicación de escritorio y registro de la barra de navegación.
    
- `config/`: Constantes y configuración global (`config.py`).
    
- `controladores/`: Orquestadores de casos de uso y lógica de aplicación (`orquestador_core.py`, `orquestador_ventas.py`, etc.).
    
- `dominio/`: Entidades de negocio y reglas de dominio (`entidades_stock.py`, `entidades_rrhh.py`, etc.).
    
- `infraestructura/`: Repositorios de persistencia y gestión de base de datos SQLite con claves foráneas activas.
    
- `vistas/`: Modulos de interfaz gráfica Tkinter / ttk (`ui_panel.py`, `ui_inventario.py`, `ui_facturacion.py`, `ui_empleados.py`, `ui_haberes.py`, `ui_clientes.py`, `ui_proveedores.py`) y hoja de estilos global (`estilos.py`).
    
- `db/`: Esquema de base de datos SQL (`esquema.sql`) e inicializador de estructura.
    
- `tests/`: Suite de pruebas unitarias e integrales con ejecutor unificado (`run_all.py`).
    
## Guía de Instalación y Uso

### 1. Clonar el repositorio

```
git clone https://github.com/aliciablopez/secza_frankie_gestion.git
cd secza_frankie_gestion
```

### 2. Crear y activar el entorno virtual

En Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
```
En Linux / macOS:

```
python3 -m venv .venv
source .venv/bin/activate
```
### 3. Ejecutar la aplicación

```
python main.py
```
### 4. Ejecutar la suite de pruebas

```
python -m tests.run_all
```
