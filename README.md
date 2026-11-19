# secza_frankie

Sistema de gestión organizado bajo principios de Clean Architecture.

## Estructura principal
- `config/`: Parámetros y constantes globales (`config.py`).
- `controladores/`: Orquestadores de casos de uso (`orquestador_core.py`, `orquestador_ventas.py`, etc.).
- `dominio/`: Entidades y reglas del negocio.
- `infraestructura/`: Conexión a base de datos, repositorios y persistencia.
- `vistas/`: Interfaz gráfica.
- `db/`: Esquema SQL (`esquema.sql`) y base de datos local.